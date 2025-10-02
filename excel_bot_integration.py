#!/usr/bin/env python3
"""Интеграция Excel генератора отчетов с Telegram ботом
Добавляет кнопки экспорта DDS и P&L таблиц к существующим отчетам
"""

import logging
import os
from datetime import datetime
from datetime import datetime as dt

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from cost_data_processor import cost_processor
from real_data_reports import generate_cumulative_financial_report, generate_real_financial_report

from excel_report_generator import excel_generator
from staged_processor import staged_processor

logger = logging.getLogger(__name__)


def format_staged_result_to_report(result: dict, date_from: str, date_to: str) -> str:
    """Форматирование результата этапной обработки в текст отчета"""
    try:
        total_revenue = result.get("total_revenue", 0)
        total_units = result.get("total_units", 0)
        net_profit = result.get("net_profit", 0)

        wb_data = result.get("wb_data", {})
        ozon_data = result.get("ozon_data", {})

        period_days = (dt.strptime(date_to, "%Y-%m-%d") - dt.strptime(date_from, "%Y-%m-%d")).days

        # Рассчитываем дополнительные метрики
        profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
        daily_revenue = total_revenue / period_days if period_days > 0 else 0

        report = f"""📊 <b>ФИНАНСОВЫЙ ОТЧЕТ</b>
🗓 Период: {date_from} — {date_to} ({period_days} дней)
⚡ Обработано этапной системой с кешированием

🎯 <b>ОСНОВНЫЕ ПОКАЗАТЕЛИ</b>
💰 Общая выручка: <b>{total_revenue:,.0f} ₽</b>
📦 Всего единиц: <b>{total_units:,}</b>
🎯 Чистая прибыль: <b>{net_profit:,.0f} ₽</b>
📊 Маржинальность: <b>{profit_margin:.1f}%</b>
📈 Среднедневная выручка: <b>{daily_revenue:,.0f} ₽</b>

🟣 <b>WILDBERRIES</b>
• 📋 Заказов: {wb_data.get('orders_count', 0):,}
• ✅ Продаж: {wb_data.get('sales_count', 0):,}
• 💰 Выручка: {wb_data.get('revenue', 0):,.0f} ₽
• 📊 Процент выкупа: {wb_data.get('buyout_rate', 0):.1f}%
• 🎯 Реклама: {wb_data.get('advertising_spend', 0):,.0f} ₽

🔵 <b>OZON</b>
• 📦 Операций: {ozon_data.get('units', 0):,}
• 💰 Выручка: {ozon_data.get('revenue', 0):,.0f} ₽
• 📊 FBO заказов: {ozon_data.get('fbo_orders_count', 0):,}
• 📈 FBS транзакций: {ozon_data.get('fbs_transactions_count', 0):,}

⚡ <b>ПРОИЗВОДИТЕЛЬНОСТЬ</b>
✅ Использовано кеширование промежуточных результатов
✅ Этапная обработка: WB → Ozon → Агрегация
✅ Все данные получены из реальных API
🕐 Обработано: {result.get('processing_completed_at', 'н/д')}

🔥 Данные актуальны и получены без фейков!"""

        return report

    except Exception as e:
        logger.error(f"Ошибка форматирования результата этапной обработки: {e}")
        return f"""📊 <b>ФИНАНСОВЫЙ ОТЧЕТ</b>
🗓 Период: {date_from} — {date_to}

❌ Ошибка форматирования результата: {str(e)[:200]}

Базовые данные:
💰 Выручка: {result.get('total_revenue', 0):,.0f} ₽
📦 Единиц: {result.get('total_units', 0):,}
🎯 Прибыль: {result.get('net_profit', 0):,.0f} ₽"""


def add_excel_export_buttons(
    existing_markup: InlineKeyboardMarkup | None = None,
    date_from: str = None,
    date_to: str = None,
    context: str = "financial",
) -> InlineKeyboardMarkup:
    """Добавляет кнопки экспорта Excel к существующей клавиатуре

    Args:
        existing_markup: Существующая клавиатура (если есть)
        date_from: Дата начала периода
        date_to: Дата окончания периода
        context: Контекст отчета ('financial' или 'cumulative')

    """
    if existing_markup is None:
        markup = InlineKeyboardMarkup()
    else:
        markup = existing_markup

    # Добавляем кнопки экспорта Excel
    if date_from and date_to:
        markup.add(
            InlineKeyboardButton(
                "📊 DDS Excel", callback_data=f"export_dds_excel:{date_from}:{date_to}:{context}"
            ),
            InlineKeyboardButton(
                "📈 P&L Excel", callback_data=f"export_pnl_excel:{date_from}:{date_to}:{context}"
            ),
        )

    # Кнопка для загрузки шаблона себестоимости
    markup.add(
        InlineKeyboardButton("💰 Загрузить себестоимость", callback_data="upload_cost_template")
    )

    return markup


async def generate_enhanced_financial_report(
    date_from: str, date_to: str, progress_message: types.Message = None
) -> tuple[str, InlineKeyboardMarkup]:
    """Генерация улучшенного финансового отчета с кнопками экспорта

    Args:
        date_from: Начальная дата периода
        date_to: Конечная дата периода
        progress_message: Сообщение для обновления прогресса (для больших периодов)

    Returns:
        Tuple[str, InlineKeyboardMarkup]: (текст отчета, клавиатура с кнопками)

    """
    # Определяем размер периода для выбора метода обработки
    start_date = dt.strptime(date_from, "%Y-%m-%d")
    end_date = dt.strptime(date_to, "%Y-%m-%d")
    period_days = (end_date - start_date).days

    logger.info(f"Генерация финансового отчета за {period_days} дней ({date_from} - {date_to})")

    # Для больших периодов (больше 60 дней) используем новую этапную систему
    if period_days > 60:
        logger.info(f"🚀 Большой период ({period_days} дней) - используем этапную обработку")
        try:
            # Используем новую этапную систему с красивым прогресс-баром
            result = await staged_processor.process_year_staged(
                date_from, date_to, progress_message
            )

            # Генерируем текст отчета из результата этапной обработки
            report_text = format_staged_result_to_report(result, date_from, date_to)
        except Exception as e:
            logger.error(f"Ошибка этапной обработки: {e}")
            # Fallback на старую систему
            report_text = await generate_real_financial_report(date_from, date_to, progress_message)
    else:
        # For smaller periods use the existing system
        logger.info(f"Обычный период ({period_days} дней) - используем стандартную обработку")
        report_text = await generate_real_financial_report(date_from, date_to, progress_message)

    # Добавляем информацию о доступности Excel экспорта
    report_text += """

📤 <b>ЭКСПОРТ ДАННЫХ</b>
• DDS Excel - детальное движение денежных средств
• P&L Excel - анализ прибылей и убытков
• Сравнение с предыдущим периодом
• Интеграция с данными о себестоимости"""

    # Создаем клавиатуру с кнопками экспорта
    markup = add_excel_export_buttons(date_from=date_from, date_to=date_to, context="financial")

    return report_text, markup


async def generate_enhanced_cumulative_report(days: int) -> tuple[str, InlineKeyboardMarkup]:
    """Генерация улучшенного нарастающего отчета с кнопками экспорта"""
    # Генерируем базовый отчет
    report_text = await generate_cumulative_financial_report(days)

    # Вычисляем даты для экспорта
    from datetime import date, timedelta

    date_to = date.today().strftime("%Y-%m-%d")
    date_from = (date.today() - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    # Добавляем информацию о доступности Excel экспорта
    report_text += f"""

📤 <b>ЭКСПОРТ НАРАСТАЮЩЕГО ИТОГА</b>
• DDS Excel - движение ДС за {days} дней
• P&L Excel - накопленные P&L показатели
• Детальная аналитика по периодам"""

    # Создаем клавиатуру с кнопками экспорта
    markup = add_excel_export_buttons(date_from=date_from, date_to=date_to, context="cumulative")

    return report_text, markup


async def handle_dds_excel_export(callback_query: types.CallbackQuery):
    """Обработчик экспорта DDS в Excel"""
    try:
        # Парсим данные из callback
        data_parts = callback_query.data.split(":")
        if len(data_parts) < 4:
            await callback_query.answer("❌ Неверные параметры экспорта")
            return

        _, date_from, date_to, context = data_parts

        await callback_query.answer("📊 Генерирую DDS Excel отчет...")

        # Показываем статус генерации
        status_msg = await callback_query.message.reply(
            "📊 <b>Генерация DDS Excel отчета</b>\n\n"
            f"📅 Период: {date_from} — {date_to}\n"
            "🔄 Создание таблиц...",
            parse_mode="HTML",
        )

        # Генерируем Excel файл
        excel_file_path = await excel_generator.generate_dds_excel_report(date_from, date_to)

        # Отправляем файл
        if os.path.exists(excel_file_path):
            await status_msg.edit_text(
                "📊 <b>DDS Excel отчет готов!</b>\n\n"
                f"📅 Период: {date_from} — {date_to}\n"
                "📤 Отправляю файл...",
                parse_mode="HTML",
            )

            # Отправляем Excel файл
            with open(excel_file_path, "rb") as file:
                await callback_query.message.reply_document(
                    InputFile(file, filename=os.path.basename(excel_file_path)),
                    caption=f"📊 <b>DDS отчет</b>\n"
                    f"📅 Период: {date_from} — {date_to}\n"
                    f"🕐 Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                    parse_mode="HTML",
                )

            # Удаляем статусное сообщение
            await status_msg.delete()

            # Удаляем временный файл через 5 минут
            import asyncio

            asyncio.create_task(delete_file_later(excel_file_path, 300))

        else:
            await status_msg.edit_text(
                "❌ <b>Ошибка создания файла</b>\n\n"
                "Файл DDS отчета не был создан. Повторите попытку позже.",
                parse_mode="HTML",
            )

    except Exception as e:
        logger.error(f"Ошибка экспорта DDS Excel: {e}")
        await callback_query.answer("❌ Ошибка создания отчета")
        try:
            await callback_query.message.reply(
                f"❌ <b>Ошибка экспорта DDS</b>\n\n" f"<code>{e!s}</code>", parse_mode="HTML"
            )
        except:
            pass


async def handle_pnl_excel_export(callback_query: types.CallbackQuery):
    """Обработчик экспорта P&L в Excel"""
    try:
        # Парсим данные из callback
        data_parts = callback_query.data.split(":")
        if len(data_parts) < 4:
            await callback_query.answer("❌ Неверные параметры экспорта")
            return

        _, date_from, date_to, context = data_parts

        await callback_query.answer("📈 Генерирую P&L Excel отчет...")

        # Показываем статус генерации
        status_msg = await callback_query.message.reply(
            "📈 <b>Генерация P&L Excel отчета</b>\n\n"
            f"📅 Период: {date_from} — {date_to}\n"
            "🔄 Создание таблиц...",
            parse_mode="HTML",
        )

        # Получаем последний файл с данными о себестоимости
        cost_data_file = cost_processor.get_latest_cost_data_file()
        if cost_data_file:
            await status_msg.edit_text(
                "📈 <b>Генерация P&L Excel отчета</b>\n\n"
                f"📅 Период: {date_from} — {date_to}\n"
                "💰 Используются данные о себестоимости\n"
                "🔄 Создание расширенного отчета...",
                parse_mode="HTML",
            )

        # Генерируем Excel файл
        excel_file_path = await excel_generator.generate_pnl_excel_report(
            date_from, date_to, cost_data_file
        )

        # Отправляем файл
        if os.path.exists(excel_file_path):
            await status_msg.edit_text(
                "📈 <b>P&L Excel отчет готов!</b>\n\n"
                f"📅 Период: {date_from} — {date_to}\n"
                f"💰 Себестоимость: {'✅ Учтена' if cost_data_file else '❌ Не загружена'}\n"
                "📤 Отправляю файл...",
                parse_mode="HTML",
            )

            # Отправляем Excel файл
            with open(excel_file_path, "rb") as file:
                caption = (
                    f"📈 <b>P&L отчет</b>\n"
                    f"📅 Период: {date_from} — {date_to}\n"
                    f"💰 Себестоимость: {'учтена' if cost_data_file else 'базовые данные'}\n"
                    f"🕐 Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )

                await callback_query.message.reply_document(
                    InputFile(file, filename=os.path.basename(excel_file_path)),
                    caption=caption,
                    parse_mode="HTML",
                )

            # Удаляем статусное сообщение
            await status_msg.delete()

            # Удаляем временный файл через 5 минут
            import asyncio

            asyncio.create_task(delete_file_later(excel_file_path, 300))

        else:
            await status_msg.edit_text(
                "❌ <b>Ошибка создания файла</b>\n\n"
                "Файл P&L отчета не был создан. Повторите попытку позже.",
                parse_mode="HTML",
            )

    except Exception as e:
        logger.error(f"Ошибка экспорта P&L Excel: {e}")
        await callback_query.answer("❌ Ошибка создания отчета")
        try:
            await callback_query.message.reply(
                f"❌ <b>Ошибка экспорта P&L</b>\n\n" f"<code>{e!s}</code>", parse_mode="HTML"
            )
        except:
            pass


async def handle_cost_template_upload(callback_query: types.CallbackQuery):
    """Обработчик запроса на загрузку шаблона себестоимости"""
    try:
        await callback_query.answer("💰 Генерирую шаблон себестоимости...")

        # Показываем статус генерации
        status_msg = await callback_query.message.reply(
            "💰 <b>Генерация шаблона себестоимости</b>\n\n" "🔄 Сбор данных о товарах...",
            parse_mode="HTML",
        )

        # Генерируем шаблон
        from cost_template_generator import CostTemplateGenerator

        generator = CostTemplateGenerator()
        template_path = await generator.generate_cost_template()

        # Отправляем шаблон
        if os.path.exists(template_path):
            await status_msg.edit_text(
                "💰 <b>Шаблон себестоимости готов!</b>\n\n" "📤 Отправляю файл...",
                parse_mode="HTML",
            )

            with open(template_path, "rb") as file:
                await callback_query.message.reply_document(
                    InputFile(file, filename=os.path.basename(template_path)),
                    caption="💰 <b>Шаблон себестоимости</b>\n\n"
                    "📝 Заполните данные и отправьте файл обратно в бот\n"
                    "📋 Инструкции находятся внутри файла",
                    parse_mode="HTML",
                )

            # Удаляем статусное сообщение
            await status_msg.delete()

            # Удаляем временный файл через 10 минут
            import asyncio

            asyncio.create_task(delete_file_later(template_path, 600))

        else:
            await status_msg.edit_text(
                "❌ <b>Ошибка создания шаблона</b>\n\n"
                "Шаблон не был создан. Повторите попытку позже.",
                parse_mode="HTML",
            )

    except Exception as e:
        logger.error(f"Ошибка генерации шаблона себестоимости: {e}")
        await callback_query.answer("❌ Ошибка создания шаблона")
        try:
            await callback_query.message.reply(
                f"❌ <b>Ошибка генерации шаблона</b>\n\n" f"<code>{e!s}</code>", parse_mode="HTML"
            )
        except:
            pass


async def handle_cost_file_upload(message: types.Message):
    """Обработчик загрузки заполненного файла себестоимости"""
    try:
        if not message.document:
            return

        # Проверяем тип файла
        if not message.document.file_name.endswith((".xlsx", ".xls")):
            await message.reply(
                "❌ <b>Неподдерживаемый формат</b>\n\n"
                "Пожалуйста, отправьте Excel файл (.xlsx или .xls)",
                parse_mode="HTML",
            )
            return

        await message.reply(
            "💰 <b>Обработка файла себестоимости</b>\n\n" "⬇️ Скачивание файла...", parse_mode="HTML"
        )

        # Скачиваем файл
        file_info = await message.bot.get_file(message.document.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)

        # Сохраняем файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_file_path = f"/tmp/cost_template_{timestamp}.xlsx"

        with open(temp_file_path, "wb") as f:
            f.write(downloaded_file.read())

        # Обрабатываем файл
        status_msg = await message.reply(
            "💰 <b>Обработка файла себестоимости</b>\n\n" "🔄 Валидация данных...",
            parse_mode="HTML",
        )

        processed_data = await cost_processor.process_cost_template_file(temp_file_path)

        # Формируем отчет о результатах обработки
        stats = processed_data["statistics"]
        errors = processed_data["validation_errors"]

        result_text = f"""💰 <b>Файл себестоимости обработан</b>

📊 <b>РЕЗУЛЬТАТЫ:</b>
• SKU с себестоимостью: {stats['total_sku_count']}
• Переменные расходы: {stats['total_variable_costs']}
• Постоянные расходы: {stats['total_fixed_costs']}
• Ошибки валидации: {stats['validation_errors_count']}

💵 <b>Постоянные расходы в месяц:</b>
{stats['monthly_fixed_total']:,.0f} ₽"""

        if stats.get("platforms"):
            result_text += "\n\n📈 <b>По платформам:</b>"
            for platform, data in stats["platforms"].items():
                result_text += f"\n• {platform}: {data['count']} SKU"

        if errors:
            result_text += "\n\n⚠️ <b>Ошибки валидации:</b>"
            for error in errors[:3]:  # Показываем только первые 3
                result_text += f"\n• {error}"
            if len(errors) > 3:
                result_text += f"\n... и еще {len(errors) - 3} ошибок"

        result_text += "\n\n✅ <b>Данные интегрированы в систему расчетов</b>"

        await status_msg.edit_text(result_text, parse_mode="HTML")

        # Удаляем временный файл
        os.unlink(temp_file_path)

    except Exception as e:
        logger.error(f"Ошибка обработки файла себестоимости: {e}")
        await message.reply(
            f"❌ <b>Ошибка обработки файла</b>\n\n" f"<code>{e!s}</code>", parse_mode="HTML"
        )


async def delete_file_later(file_path: str, delay_seconds: int):
    """Удаление файла через заданное время"""
    import asyncio

    await asyncio.sleep(delay_seconds)
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Временный файл удален: {file_path}")
    except Exception as e:
        logger.error(f"Ошибка удаления временного файла {file_path}: {e}")


# Функции для интеграции с существующими обработчиками бота


def get_callback_handlers():
    """Возвращает словарь с обработчиками callback'ов для интеграции в основной бот"""
    return {
        "export_dds_excel": handle_dds_excel_export,
        "export_pnl_excel": handle_pnl_excel_export,
        "upload_cost_template": handle_cost_template_upload,
    }


def get_document_handler():
    """Возвращает обработчик документов для интеграции в основной бот"""
    return handle_cost_file_upload


async def generate_cost_summary_for_bot() -> str:
    """Генерация сводки по себестоимости для бота"""
    return await cost_processor.generate_cost_summary_report()


async def generate_wb_financial_report(
    date_from: str, date_to: str, progress_message: types.Message = None
) -> tuple[str, InlineKeyboardMarkup]:
    """Генерация финансового отчета только для Wildberries

    Args:
        date_from: Начальная дата периода
        date_to: Конечная дата периода
        progress_message: Сообщение для обновления прогресса

    Returns:
        Tuple[str, InlineKeyboardMarkup]: (текст отчета, клавиатура с кнопками)

    """
    # Определяем размер периода
    start_date = dt.strptime(date_from, "%Y-%m-%d")
    end_date = dt.strptime(date_to, "%Y-%m-%d")
    period_days = (end_date - start_date).days

    logger.info(f"🟣 Генерация WB отчета за {period_days} дней ({date_from} - {date_to})")

    try:
        # Для начала используем существующую функцию, но добавим маркировку WB
        from real_data_reports import generate_real_financial_report

        # Генерируем базовый отчет (пока общий, позже можно сделать WB-специфичный)
        report_text = await generate_real_financial_report(date_from, date_to, progress_message)

        # Добавляем префикс для WB
        report_text = "🟣 <b>WILDBERRIES ФИНАНСОВЫЙ ОТЧЕТ</b>\n\n" + report_text

    except Exception as e:
        logger.error(f"Ошибка генерации WB отчета: {e}")
        report_text = f"""❌ <b>ОШИБКА ГЕНЕРАЦИИ WB ОТЧЕТА</b>

🚫 Ошибка: {e!s}

📝 <b>Возможные причины:</b>
• WB API недоступен
• Проблемы с базой данных
• Некорректные параметры запроса

🔄 Повторите запрос через несколько минут"""

    # Добавляем информацию о доступности Excel экспорта для WB
    report_text += """

📤 <b>ЭКСПОРТ WB ДАННЫХ</b>
• WB DDS Excel - детальное движение денежных средств WB
• WB P&L Excel - анализ прибылей и убытков WB
• Сравнение с предыдущим периодом
• Интеграция с данными о себестоимости WB"""

    # Создаем клавиатуру с кнопками экспорта для WB
    markup = add_excel_export_buttons(date_from=date_from, date_to=date_to, context="wb_financial")

    return report_text, markup


async def generate_ozon_financial_report(
    date_from: str, date_to: str, progress_message: types.Message = None
) -> tuple[str, InlineKeyboardMarkup]:
    """Генерация финансового отчета только для Ozon

    Args:
        date_from: Начальная дата периода
        date_to: Конечная дата периода
        progress_message: Сообщение для обновления прогресса

    Returns:
        Tuple[str, InlineKeyboardMarkup]: (текст отчета, клавиатура с кнопками)

    """
    # Определяем размер периода
    start_date = dt.strptime(date_from, "%Y-%m-%d")
    end_date = dt.strptime(date_to, "%Y-%m-%d")
    period_days = (end_date - start_date).days

    logger.info(f"🟠 Генерация Ozon отчета за {period_days} дней ({date_from} - {date_to})")

    try:
        # Для начала используем существующую функцию, но добавим маркировку Ozon
        from real_data_reports import generate_real_financial_report

        # Генерируем базовый отчет (пока общий, позже можно сделать Ozon-специфичный)
        report_text = await generate_real_financial_report(date_from, date_to, progress_message)

        # Добавляем префикс для Ozon
        report_text = "🟠 <b>OZON ФИНАНСОВЫЙ ОТЧЕТ</b>\n\n" + report_text

    except Exception as e:
        logger.error(f"Ошибка генерации Ozon отчета: {e}")
        report_text = f"""❌ <b>ОШИБКА ГЕНЕРАЦИИ OZON ОТЧЕТА</b>

🚫 Ошибка: {e!s}

📝 <b>Возможные причины:</b>
• Ozon API недоступен
• Проблемы с базой данных
• Некорректные параметры запроса

🔄 Повторите запрос через несколько минут"""

    # Добавляем информацию о доступности Excel экспорта для Ozon
    report_text += """

📤 <b>ЭКСПОРТ OZON ДАННЫХ</b>
• Ozon DDS Excel - детальное движение денежных средств Ozon
• Ozon P&L Excel - анализ прибылей и убытков Ozon
• Сравнение с предыдущим периодом
• Интеграция с данными о себестоимости Ozon"""

    # Создаем клавиатуру с кнопками экспорта для Ozon
    markup = add_excel_export_buttons(
        date_from=date_from, date_to=date_to, context="ozon_financial"
    )

    return report_text, markup
