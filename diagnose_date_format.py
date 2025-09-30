#!/usr/bin/env python3
"""
ДИАГНОСТИКА ФОРМАТА ДАТ В WB API
Анализируем почему фильтрация обнуляет все данные
"""

import asyncio
import logging
from real_data_reports import RealDataFinancialReports
from api_chunking import ChunkedAPIManager
import api_clients_main as api_clients

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def diagnose_date_formats():
    """Диагностика форматов дат в WB API"""

    logger.info("🔍 ДИАГНОСТИКА ФОРМАТОВ ДАТ В WB API")
    logger.info("=" * 60)

    chunked_api = ChunkedAPIManager(api_clients)

    # Получаем сырые данные за январь без фильтрации
    date_from = "2025-01-01"
    date_to = "2025-01-31"

    logger.info(f"Запрашиваем период: {date_from} → {date_to}")
    logger.info("")

    try:
        # Получаем Sales данные
        logger.info("📊 АНАЛИЗ SALES API:")
        sales_data = await chunked_api.get_wb_sales_chunked(date_from, date_to)

        if sales_data:
            logger.info(f"Получено {len(sales_data)} записей Sales")
            logger.info("")

            # Анализируем первые 10 записей
            logger.info("🗓️ АНАЛИЗ ДАТ В SALES:")
            for i, record in enumerate(sales_data[:10]):
                raw_date = record.get('date', '')

                # Парсим дату как в системе
                if 'T' in raw_date:
                    parsed_date = raw_date.split('T')[0]
                else:
                    parsed_date = raw_date[:10]

                # Проверяем попадание в диапазон
                in_range = date_from <= parsed_date <= date_to

                logger.info(f"  Запись {i+1}: '{raw_date}' → '{parsed_date}' (в диапазоне: {in_range})")

                if i >= 5:  # Ограничиваем вывод
                    break

            # Группируем по датам
            logger.info("")
            logger.info("📈 ГРУППИРОВКА ПО ДАТАМ:")
            date_groups = {}
            in_range_count = 0
            out_range_count = 0

            for record in sales_data:
                raw_date = record.get('date', '')
                if 'T' in raw_date:
                    parsed_date = raw_date.split('T')[0]
                else:
                    parsed_date = raw_date[:10]

                if parsed_date:
                    if parsed_date not in date_groups:
                        date_groups[parsed_date] = 0
                    date_groups[parsed_date] += 1

                    # Считаем в диапазоне/вне диапазона
                    if date_from <= parsed_date <= date_to:
                        in_range_count += 1
                    else:
                        out_range_count += 1

            # Показываем статистику по датам
            sorted_dates = sorted(date_groups.keys())
            for date_key in sorted_dates[:20]:  # Показываем первые 20 дат
                count = date_groups[date_key]
                in_range = date_from <= date_key <= date_to
                status = "✅ В диапазоне" if in_range else "❌ Вне диапазона"
                logger.info(f"    {date_key}: {count} записей ({status})")

            logger.info("")
            logger.info(f"📊 ИТОГОВАЯ СТАТИСТИКА:")
            logger.info(f"    Всего записей: {len(sales_data)}")
            logger.info(f"    В диапазоне: {in_range_count}")
            logger.info(f"    Вне диапазона: {out_range_count}")
            logger.info(f"    Минимальная дата: {min(sorted_dates) if sorted_dates else 'N/A'}")
            logger.info(f"    Максимальная дата: {max(sorted_dates) if sorted_dates else 'N/A'}")

            # Проверяем priceWithDisc для записей в диапазоне
            logger.info("")
            logger.info("💰 АНАЛИЗ СУММ ДЛЯ ЗАПИСЕЙ В ДИАПАЗОНЕ:")
            total_in_range = 0
            total_out_range = 0

            for record in sales_data:
                raw_date = record.get('date', '')
                if 'T' in raw_date:
                    parsed_date = raw_date.split('T')[0]
                else:
                    parsed_date = raw_date[:10]

                price = record.get('priceWithDisc', 0) or 0

                if date_from <= parsed_date <= date_to:
                    total_in_range += price
                else:
                    total_out_range += price

            logger.info(f"    Сумма в диапазоне: {total_in_range:,.0f} ₽")
            logger.info(f"    Сумма вне диапазона: {total_out_range:,.0f} ₽")
            logger.info(f"    Общая сумма: {total_in_range + total_out_range:,.0f} ₽")

        else:
            logger.warning("Нет данных Sales")

        logger.info("")
        logger.info("=" * 60)

        # Аналогично для Orders
        logger.info("📊 АНАЛИЗ ORDERS API:")
        orders_data = await chunked_api.get_wb_orders_chunked(date_from, date_to)

        if orders_data:
            logger.info(f"Получено {len(orders_data)} записей Orders")

            # Анализируем даты Orders
            orders_date_groups = {}
            orders_in_range = 0
            orders_out_range = 0

            for record in orders_data:
                raw_date = record.get('date', '')
                if 'T' in raw_date:
                    parsed_date = raw_date.split('T')[0]
                else:
                    parsed_date = raw_date[:10]

                if parsed_date:
                    if parsed_date not in orders_date_groups:
                        orders_date_groups[parsed_date] = 0
                    orders_date_groups[parsed_date] += 1

                    if date_from <= parsed_date <= date_to:
                        orders_in_range += 1
                    else:
                        orders_out_range += 1

            logger.info(f"    В диапазоне: {orders_in_range}")
            logger.info(f"    Вне диапазона: {orders_out_range}")

            if orders_date_groups:
                sorted_orders_dates = sorted(orders_date_groups.keys())
                logger.info(f"    Минимальная дата: {min(sorted_orders_dates)}")
                logger.info(f"    Максимальная дата: {max(sorted_orders_dates)}")

        else:
            logger.warning("Нет данных Orders")

        logger.info("")
        logger.info("🎯 РЕКОМЕНДАЦИИ:")

        if in_range_count == 0 and sales_data:
            logger.warning("❌ НИ ОДНОЙ записи Sales не попадает в диапазон!")
            logger.warning("    Проблема в фильтрации - слишком строгая")
            logger.warning("    Нужно расширить диапазон или изменить логику фильтрации")
        elif in_range_count > 0:
            logger.info("✅ Часть записей попадает в диапазон")
            logger.info(f"    Ожидаемая сумма после фильтрации: {total_in_range:,.0f} ₽")

        return {
            'sales_total': len(sales_data) if sales_data else 0,
            'sales_in_range': in_range_count,
            'sales_out_range': out_range_count,
            'sum_in_range': total_in_range if 'total_in_range' in locals() else 0,
            'sum_out_range': total_out_range if 'total_out_range' in locals() else 0,
            'date_range_issue': in_range_count == 0 and sales_data is not None
        }

    except Exception as e:
        logger.error(f"❌ Ошибка диагностики: {e}")
        return None

if __name__ == "__main__":
    result = asyncio.run(diagnose_date_formats())