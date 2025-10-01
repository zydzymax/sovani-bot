#!/usr/bin/env python3
"""Автоматический процессор отзывов"""

import asyncio
import logging

from wb_reviews_manager import WBReview, reviews_manager

logger = logging.getLogger(__name__)


class AutoReviewsProcessor:
    """Автоматический процессор отзывов"""

    def __init__(self, bot=None):
        self.bot = bot
        self.processing = False
        self.check_interval = 43200  # 12 часов (2 раза в день)
        self.admin_chat_id = None  # ID чата администратора

    def set_admin_chat_id(self, chat_id: int):
        """Установка ID чата администратора для уведомлений"""
        self.admin_chat_id = chat_id

    async def start_auto_processing(self):
        """Запуск автоматической обработки отзывов"""
        if self.processing:
            logger.warning("Автообработка отзывов уже запущена")
            return

        self.processing = True
        logger.info("Запуск автоматической обработки отзывов")

        while self.processing:
            try:
                await self._process_reviews_cycle()
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Ошибка в цикле автообработки отзывов: {e}")
                await asyncio.sleep(60)  # Короткая пауза при ошибке

    async def stop_auto_processing(self):
        """Остановка автоматической обработки"""
        self.processing = False
        logger.info("Автообработка отзывов остановлена")

    async def process_all_unanswered_reviews(self):
        """Первичная обработка всех неотвеченных отзывов
        Вызывается при старте бота
        """
        try:
            logger.info("🚀 ПЕРВИЧНАЯ ОБРАБОТКА: Ищем все неотвеченные отзывы...")

            # Получаем все неотвеченные отзывы (без ограничения)
            unanswered_reviews = await reviews_manager.get_all_unanswered_reviews()

            if not unanswered_reviews:
                logger.info("✅ Все отзывы уже имеют ответы")
                if self.bot and self.admin_chat_id:
                    await self.bot.send_message(
                        self.admin_chat_id,
                        "✅ <b>Первичная проверка завершена</b>\n\n"
                        "Все отзывы уже имеют ответы. Новые отзывы будут обрабатываться автоматически.",
                    )
                return

            logger.info(f"📋 Найдено {len(unanswered_reviews)} неотвеченных отзывов")

            # Разделяем отзывы на автоответы и ручную проверку
            auto_reviews = []
            manual_reviews = []

            for review in unanswered_reviews:
                if reviews_manager.should_auto_respond(review):
                    auto_reviews.append(review)
                else:
                    manual_reviews.append(review)

            logger.info(
                f"📊 Анализ отзывов: {len(auto_reviews)} автоответ, {len(manual_reviews)} ручная проверка"
            )

            # Обрабатываем автоответы
            auto_processed = 0
            if auto_reviews:
                auto_processed = await self._process_auto_reviews(auto_reviews)

            # Уведомляем администратора о результатах
            if self.bot and self.admin_chat_id:
                message = "🎯 <b>Первичная обработка завершена</b>\n\n"
                message += f"📋 Всего неотвеченных отзывов: {len(unanswered_reviews)}\n"
                message += f"✅ Автоматически обработано: {auto_processed}\n"
                message += f"⚠️ Требует ручной проверки: {len(manual_reviews)}\n\n"

                if manual_reviews:
                    message += "📝 <b>Отзывы для ручной проверки:</b>\n"
                    for review in manual_reviews[:5]:  # Показываем первые 5
                        stars = "⭐" * review.rating
                        message += f"• {stars} {review.text[:50]}...\n"

                    if len(manual_reviews) > 5:
                        message += f"... и еще {len(manual_reviews) - 5} отзывов\n"

                    message += "\n💡 Используйте команду /reviews для обработки"

                await self.bot.send_message(self.admin_chat_id, message)

            return {
                "total_found": len(unanswered_reviews),
                "auto_processed": auto_processed,
                "manual_needed": len(manual_reviews),
            }

        except Exception as e:
            logger.error(f"Ошибка первичной обработки отзывов: {e}")
            if self.bot and self.admin_chat_id:
                await self.bot.send_message(
                    self.admin_chat_id, f"❌ <b>Ошибка первичной обработки отзывов</b>\n\n{e}"
                )
            raise

    async def _process_reviews_cycle(self):
        """Один цикл обработки отзывов"""
        try:
            logger.info("🔄 Проверка новых отзывов...")

            # Получаем новые отзывы
            reviews = await reviews_manager.get_new_reviews(limit=50)

            if not reviews:
                logger.info("Новых отзывов не найдено")
                return

            # Разделяем отзывы
            auto_reviews = [r for r in reviews if reviews_manager.should_auto_respond(r)]
            manual_reviews = [r for r in reviews if reviews_manager.needs_user_approval(r)]

            logger.info(
                f"Найдено {len(reviews)} отзывов: {len(auto_reviews)} автоответ, {len(manual_reviews)} ручная проверка"
            )

            # Обрабатываем автоответы
            if auto_reviews:
                await self._process_auto_reviews(auto_reviews)

            # Уведомляем о отзывах для ручной проверки
            if manual_reviews and self.bot and self.admin_chat_id:
                await self._notify_manual_reviews(manual_reviews)

        except Exception as e:
            logger.error(f"Ошибка цикла обработки отзывов: {e}")

    async def _process_auto_reviews(self, auto_reviews: list[WBReview]):
        """Автоматическая обработка отзывов 4-5 звезд"""
        processed_count = 0
        failed_count = 0

        for review in auto_reviews:
            try:
                # Обрабатываем отзыв
                result = await reviews_manager.process_review(review)

                if result["auto_respond"]:
                    # Отправляем ответ автоматически
                    success = await reviews_manager.send_review_response(
                        review.id, result["generated_response"]
                    )

                    if success:
                        processed_count += 1
                        logger.info(
                            f"✅ Автоответ отправлен на отзыв {review.id} ({review.rating}⭐)"
                        )
                        logger.info(f"Ответ: {result['generated_response'][:100]}...")
                    else:
                        failed_count += 1
                        logger.error(f"❌ Ошибка отправки ответа на отзыв {review.id}")

                await asyncio.sleep(2)  # Пауза между отправками

            except Exception as e:
                failed_count += 1
                logger.error(f"Ошибка автообработки отзыва {review.id}: {e}")

        if processed_count > 0 or failed_count > 0:
            logger.info(
                f"Автообработка завершена: ✅{processed_count} успешно, ❌{failed_count} ошибок"
            )

            # Уведомляем администратора о результатах
            if self.bot and self.admin_chat_id:
                try:
                    stats_text = f"🤖 Автообработка отзывов:\n✅ Отвечено: {processed_count}\n❌ Ошибок: {failed_count}"
                    await self.bot.send_message(self.admin_chat_id, stats_text)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления: {e}")

    async def _notify_manual_reviews(self, manual_reviews: list[WBReview]):
        """Уведомление о отзывах, требующих ручной проверки"""
        try:
            negative_count = len([r for r in manual_reviews if r.rating <= 2])
            neutral_count = len([r for r in manual_reviews if r.rating == 3])

            notification_text = "⚠️ Новые отзывы требуют проверки:\n"
            notification_text += f"🔴 Негативные (1-2⭐): {negative_count}\n"
            notification_text += f"🟡 Нейтральные (3⭐): {neutral_count}\n\n"
            notification_text += "Используйте /reviews для просмотра"

            await self.bot.send_message(self.admin_chat_id, notification_text)

        except Exception as e:
            logger.error(f"Ошибка уведомления о ручных отзывах: {e}")

    async def force_check_reviews(self) -> dict:
        """Принудительная проверка отзывов"""
        try:
            reviews = await reviews_manager.get_new_reviews(limit=50)

            auto_reviews = [r for r in reviews if reviews_manager.should_auto_respond(r)]
            manual_reviews = [r for r in reviews if reviews_manager.needs_user_approval(r)]

            # Обрабатываем автоответы
            auto_processed = 0
            if auto_reviews:
                for review in auto_reviews:
                    result = await reviews_manager.process_review(review)
                    if result["auto_respond"]:
                        success = await reviews_manager.send_review_response(
                            review.id, result["generated_response"]
                        )
                        if success:
                            auto_processed += 1

            return {
                "total_reviews": len(reviews),
                "auto_processed": auto_processed,
                "manual_needed": len(manual_reviews),
                "manual_reviews": manual_reviews,
            }

        except Exception as e:
            logger.error(f"Ошибка принудительной проверки: {e}")
            return {"error": str(e)}


# Глобальный экземпляр автопроцессора
auto_processor = AutoReviewsProcessor()
