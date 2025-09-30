#!/usr/bin/env python3
"""
Обработчики бота для работы с отзывами
"""

import asyncio
import json
import logging
from typing import Dict, List, Any

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from wb_reviews_manager import reviews_manager, WBReview

logger = logging.getLogger(__name__)

class ReviewsBotHandlers:
    """Обработчики бота для работы с отзывами"""

    @staticmethod
    async def handle_reviews_command(message: types.Message):
        """Обработка команды /reviews"""
        try:
            await message.answer("🔄 Проверяю новые отзывы...")

            # Получаем новые отзывы
            reviews = await reviews_manager.get_new_reviews(limit=20)

            if not reviews:
                await message.answer("📝 Новых отзывов не найдено")
                return

            # Разделяем отзывы по типам обработки
            auto_reviews = [r for r in reviews if reviews_manager.should_auto_respond(r)]
            manual_reviews = [r for r in reviews if reviews_manager.needs_user_approval(r)]

            stats_text = f"📊 Найдено {len(reviews)} новых отзывов:\n"
            stats_text += f"✅ Автоответ (4-5⭐): {len(auto_reviews)}\n"
            stats_text += f"⚠️ Требуют проверки (1-3⭐): {len(manual_reviews)}"

            await message.answer(stats_text)

            # Обрабатываем автоответы
            if auto_reviews:
                await ReviewsBotHandlers._process_auto_reviews(message, auto_reviews)

            # Показываем отзывы для ручной проверки
            if manual_reviews:
                await ReviewsBotHandlers._show_manual_reviews(message, manual_reviews)

        except Exception as e:
            logger.error(f"Ошибка обработки команды reviews: {e}")
            await message.answer(f"❌ Ошибка: {e}")

    @staticmethod
    async def handle_all_unanswered_reviews_command(message: types.Message):
        """Обработка команды /all_reviews - все неотвеченные отзывы"""
        try:
            await message.answer("🔄 Получаю ВСЕ неотвеченные отзывы...\n⏳ Это может занять некоторое время...")

            # Получаем ВСЕ неотвеченные отзывы
            reviews = await reviews_manager.get_all_unanswered_reviews(limit=200)

            if not reviews:
                await message.answer("📝 Неотвеченных отзывов не найдено")
                return

            # Разделяем отзывы по типам обработки
            auto_reviews = [r for r in reviews if reviews_manager.should_auto_respond(r)]
            manual_reviews = [r for r in reviews if reviews_manager.needs_user_approval(r)]

            stats_text = f"📊 Найдено {len(reviews)} неотвеченных отзывов:\n"
            stats_text += f"✅ Автоответ (4-5⭐): {len(auto_reviews)}\n"
            stats_text += f"⚠️ Требуют проверки (1-3⭐): {len(manual_reviews)}\n\n"
            stats_text += f"🔄 Начинаю обработку..."

            await message.answer(stats_text)

            # Обрабатываем автоответы пакетами
            if auto_reviews:
                await ReviewsBotHandlers._process_auto_reviews_batch(message, auto_reviews)

            # Показываем первые 10 отзывов для ручной проверки
            if manual_reviews:
                await message.answer(f"⚠️ Показываю первые 10 отзывов для ручной проверки из {len(manual_reviews)}")
                await ReviewsBotHandlers._show_manual_reviews(message, manual_reviews[:10])

                if len(manual_reviews) > 10:
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(
                        InlineKeyboardButton("📋 Показать еще отзывы",
                                           callback_data="show_more_manual_reviews")
                    )
                    await message.answer(f"Осталось {len(manual_reviews) - 10} отзывов для проверки",
                                       reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Ошибка обработки команды all_reviews: {e}")
            await message.answer(f"❌ Ошибка: {e}")

    @staticmethod
    async def _process_auto_reviews_batch(message: types.Message, auto_reviews: List[WBReview]):
        """Пакетная автоматическая обработка отзывов 4-5 звезд"""
        processed_count = 0
        total_count = len(auto_reviews)

        # Обрабатываем пакетами по 5 отзывов
        batch_size = 5
        for i in range(0, len(auto_reviews), batch_size):
            batch = auto_reviews[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_count + batch_size - 1) // batch_size

            await message.answer(f"🔄 Обрабатываю пакет {batch_num}/{total_batches} ({len(batch)} отзывов)")

            for review in batch:
                try:
                    # Обрабатываем отзыв
                    result = await reviews_manager.process_review(review)

                    if result['auto_respond']:
                        # Отправляем ответ автоматически
                        success = await reviews_manager.send_review_response(
                            review.id,
                            result['generated_response']
                        )

                        if success:
                            processed_count += 1
                            logger.info(f"Автоответ отправлен на отзыв {review.id}")

                    # Небольшая задержка между отзывами
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Ошибка автообработки отзыва {review.id}: {e}")

            # Задержка между пакетами
            if i + batch_size < len(auto_reviews):
                await asyncio.sleep(5)

        await message.answer(f"✅ Автоматически отвечено на {processed_count} из {total_count} отзывов")

    @staticmethod
    async def _process_auto_reviews(message: types.Message, auto_reviews: List[WBReview]):
        """Автоматическая обработка отзывов 4-5 звезд"""
        processed_count = 0

        for review in auto_reviews:
            try:
                # Обрабатываем отзыв
                result = await reviews_manager.process_review(review)

                if result['auto_respond']:
                    # Отправляем ответ автоматически
                    success = await reviews_manager.send_review_response(
                        review.id,
                        result['generated_response']
                    )

                    if success:
                        processed_count += 1
                        logger.info(f"Автоответ отправлен на отзыв {review.id}")

            except Exception as e:
                logger.error(f"Ошибка автообработки отзыва {review.id}: {e}")

        if processed_count > 0:
            await message.answer(f"✅ Автоматически отвечено на {processed_count} отзывов")

    @staticmethod
    async def _show_manual_reviews(message: types.Message, manual_reviews: List[WBReview]):
        """Показ отзывов для ручной проверки"""
        for review in manual_reviews:
            try:
                # Генерируем предварительный ответ
                result = await reviews_manager.process_review(review)

                # Формируем сообщение с отзывом
                review_text = ReviewsBotHandlers._format_review_message(review, result['generated_response'])

                # Создаем клавиатуру
                keyboard = ReviewsBotHandlers._create_review_keyboard(review.id)

                await message.answer(review_text, reply_markup=keyboard, parse_mode='HTML')

            except Exception as e:
                logger.error(f"Ошибка показа отзыва {review.id}: {e}")

    @staticmethod
    def _format_review_message(review: WBReview, suggested_response: str) -> str:
        """Форматирование сообщения с отзывом"""
        stars = "⭐" * review.rating + "☆" * (5 - review.rating)

        media_info = ""
        if review.has_photos:
            media_info += "📸 "
        if review.has_videos:
            media_info += "🎥 "

        message = f"""<b>🔍 Отзыв требует проверки</b>

<b>👤 Покупатель:</b> {review.customer_name}
<b>🛍️ Товар:</b> {review.product_name}
<b>⭐ Оценка:</b> {stars} ({review.rating}/5)
<b>📅 Дата:</b> {review.created_at[:10] if review.created_at else 'н/д'}
{media_info}

<b>💬 Отзыв:</b>
<i>"{review.text}"</i>

<b>🤖 Предлагаемый ответ:</b>
<i>"{suggested_response}"</i>"""

        return message

    @staticmethod
    def _create_review_keyboard(review_id: str) -> InlineKeyboardMarkup:
        """Создание клавиатуры для отзыва"""
        keyboard = InlineKeyboardMarkup(row_width=2)

        keyboard.add(
            InlineKeyboardButton("✅ Ответить", callback_data=f"review_approve:{review_id}"),
            InlineKeyboardButton("✏️ Исправить", callback_data=f"review_edit:{review_id}")
        )

        keyboard.add(
            InlineKeyboardButton("❌ Пропустить", callback_data=f"review_skip:{review_id}")
        )

        return keyboard

    @staticmethod
    async def handle_review_approve(callback_query: types.CallbackQuery):
        """Обработка одобрения ответа на отзыв"""
        try:
            review_id = callback_query.data.split(':')[1]

            # Находим сообщение с отзывом и извлекаем предлагаемый ответ
            message_text = callback_query.message.text or callback_query.message.caption

            # Извлекаем предлагаемый ответ из сообщения
            suggested_response = ReviewsBotHandlers._extract_suggested_response(message_text)

            if suggested_response:
                # Отправляем ответ
                success = await reviews_manager.send_review_response(review_id, suggested_response)

                if success:
                    await callback_query.message.edit_text(
                        f"✅ Ответ отправлен!\n\n{message_text}\n\n<b>📤 ОТПРАВЛЕНО:</b> {suggested_response}",
                        parse_mode='HTML'
                    )
                    await callback_query.answer("✅ Ответ отправлен!")
                else:
                    await callback_query.answer("❌ Ошибка отправки ответа", show_alert=True)
            else:
                await callback_query.answer("❌ Не удалось извлечь текст ответа", show_alert=True)

        except Exception as e:
            logger.error(f"Ошибка одобрения отзыва: {e}")
            await callback_query.answer("❌ Ошибка обработки", show_alert=True)

    @staticmethod
    async def handle_review_edit(callback_query: types.CallbackQuery):
        """Обработка запроса на редактирование ответа"""
        try:
            review_id = callback_query.data.split(':')[1]

            # Переходим в режим редактирования
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("❌ Отменить редактирование",
                                   callback_data=f"review_cancel_edit:{review_id}")
            )

            await callback_query.message.edit_reply_markup(reply_markup=keyboard)

            await callback_query.message.reply(
                "✏️ Напишите исправленный ответ на отзыв:",
                reply_markup=types.ForceReply(selective=True)
            )

            await callback_query.answer("✏️ Режим редактирования активирован")

        except Exception as e:
            logger.error(f"Ошибка активации редактирования: {e}")
            await callback_query.answer("❌ Ошибка", show_alert=True)

    @staticmethod
    async def handle_review_skip(callback_query: types.CallbackQuery):
        """Обработка пропуска отзыва"""
        try:
            review_id = callback_query.data.split(':')[1]

            await callback_query.message.edit_text(
                f"⏭️ Отзыв пропущен\n\n{callback_query.message.text}",
                parse_mode='HTML'
            )

            await callback_query.answer("⏭️ Отзыв пропущен")

        except Exception as e:
            logger.error(f"Ошибка пропуска отзыва: {e}")
            await callback_query.answer("❌ Ошибка", show_alert=True)

    @staticmethod
    def _extract_suggested_response(message_text: str) -> str:
        """Извлечение предлагаемого ответа из текста сообщения"""
        try:
            # Ищем текст между "🤖 Предлагаемый ответ:" и концом сообщения
            start_marker = "🤖 Предлагаемый ответ:"
            start_idx = message_text.find(start_marker)

            if start_idx == -1:
                return ""

            # Находим начало ответа (после маркера и тегов)
            response_start = message_text.find('"', start_idx) + 1
            response_end = message_text.rfind('"')

            if response_start > 0 and response_end > response_start:
                return message_text[response_start:response_end]

            return ""

        except Exception as e:
            logger.error(f"Ошибка извлечения ответа: {e}")
            return ""

    @staticmethod
    async def handle_edit_response_message(message: types.Message):
        """Обработка исправленного ответа пользователя"""
        try:
            # Проверяем, что это ответ на сообщение с отзывом
            if not message.reply_to_message:
                return

            reply_text = message.reply_to_message.text
            if "✏️ Напишите исправленный ответ" not in reply_text:
                return

            # Извлекаем review_id из исходного сообщения
            # Нужно найти более надежный способ связать сообщения
            edited_response = message.text

            # Отправляем исправленный ответ
            await message.answer(f"✅ Исправленный ответ принят:\n\n<i>'{edited_response}'</i>",
                               parse_mode='HTML')

            # TODO: Здесь нужно отправить исправленный ответ через API
            # await reviews_manager.send_review_response(review_id, edited_response)

        except Exception as e:
            logger.error(f"Ошибка обработки исправленного ответа: {e}")

# Инициализация обработчиков
async def setup_reviews_handlers(dp):
    """Настройка обработчиков отзывов для диспетчера"""

    # Команда /reviews
    dp.register_message_handler(
        ReviewsBotHandlers.handle_reviews_command,
        commands=['reviews']
    )

    # Команда /all_reviews - все неотвеченные отзывы
    dp.register_message_handler(
        ReviewsBotHandlers.handle_all_unanswered_reviews_command,
        commands=['all_reviews']
    )

    # Callback handlers для отзывов
    dp.register_callback_query_handler(
        ReviewsBotHandlers.handle_review_approve,
        lambda c: c.data.startswith('review_approve:')
    )

    dp.register_callback_query_handler(
        ReviewsBotHandlers.handle_review_edit,
        lambda c: c.data.startswith('review_edit:')
    )

    dp.register_callback_query_handler(
        ReviewsBotHandlers.handle_review_skip,
        lambda c: c.data.startswith('review_skip:')
    )

    # Обработка исправленных ответов
    dp.register_message_handler(
        ReviewsBotHandlers.handle_edit_response_message,
        content_types=['text'],
        state='*'
    )

    logger.info("Обработчики отзывов настроены")