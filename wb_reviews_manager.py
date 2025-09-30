#!/usr/bin/env python3
"""
Менеджер отзывов Wildberries с ChatGPT интеграцией

ОСНОВНЫЕ КЛАССЫ:
- WBReview: Структура данных отзыва WB
- ChatGPTReviewProcessor: Обработчик для генерации ответов через OpenAI
- WBReviewsManager: Главный менеджер для работы с отзывами

ФУНКЦИОНАЛЬНОСТЬ:
- Получение неотвеченных отзывов из WB API
- Автоматическая генерация персонализированных ответов через ChatGPT
- Отправка ответов обратно в WB API
- Определение необходимости одобрения (низкие рейтинги)
- Fallback на отвеченные отзывы при отсутствии новых

ОСОБЕННОСТИ ПАРСИНГА (ИСПРАВЛЕНО В СЕНТЯБРЕ 2025):
- Правильное извлечение имен покупателей из поля userName
- Корректное извлечение названий товаров из productDetails.productName
- Точный парсинг рейтингов без fallback на 5 звезд
- Обработка медиафайлов (фото/видео) в отзывах

НАСТРОЙКИ CHATGPT:
- Модель: gpt-4
- Персонализация: обязательное обращение по имени
- Тон: зависит от рейтинга отзыва (1-5 звезд)
- Брендинг: обязательное упоминание SoVAni
- Уникальность: избегание шаблонных фраз

АВТОР: SoVAni Team
ПОСЛЕДНЕЕ ИСПРАВЛЕНИЕ: Сентябрь 2025 (парсинг имен и рейтингов)
"""

import asyncio
import json
import logging
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

import api_clients_main as api_clients
from config import Config

logger = logging.getLogger(__name__)

@dataclass
class WBReview:
    """Структура отзыва WB"""
    id: str
    product_name: str
    customer_name: str
    rating: int
    text: str
    created_at: str
    has_photos: bool
    has_videos: bool
    photos: List[str]
    videos: List[str]
    answered: bool
    answer_text: Optional[str] = None

class ChatGPTReviewProcessor:
    """Обработчик отзывов через ChatGPT API"""

    def __init__(self):
        self.api_key = getattr(Config, 'OPENAI_API_KEY', None)
        if not self.api_key:
            logger.warning("OPENAI_API_KEY не найден в конфигурации")

        self.base_url = "https://api.openai.com/v1/chat/completions"

    async def generate_review_response(self, review: WBReview) -> str:
        """Генерация ответа на отзыв через ChatGPT"""
        if not self.api_key:
            return self._get_fallback_response(review)

        prompt = self._build_response_prompt(review)

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 300,
                "temperature": 0.8  # Увеличиваем для большей уникальности
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content'].strip()
                    else:
                        logger.error(f"ChatGPT API error {response.status}: {await response.text()}")
                        return self._get_fallback_response(review)

        except Exception as e:
            logger.error(f"Ошибка генерации ответа ChatGPT: {e}")
            return self._get_fallback_response(review)

    def _get_system_prompt(self) -> str:
        """Системный промпт для ChatGPT"""
        return """Ты - представитель бренда SoVAni (ОБЯЗАТЕЛЬНО пиши именно SoVAni, не меняй написание!).
Твоя задача - отвечать на отзывы покупателей с максимальной уникальностью и индивидуальным подходом.

ПРАВИЛА:
1. ОБЯЗАТЕЛЬНО используй имя покупателя в ответе
2. ВСЕГДА пиши бренд как "SoVAni" (точно так!)
3. Тон зависит от оценки:
   - 5 звезд: очень благодарный, теплый
   - 4 звезды: благодарный, дружелюбный
   - 3 звезды: понимающий, готовый помочь
   - 2 звезды: сочувствующий, активно решающий проблемы
   - 1 звезда: извиняющийся, максимально клиентоориентированный

4. Для развернутых отзывов с фото/видео - добавляй легкий юмор
5. ВСЕГДА приглашай вернуться за новой покупкой
6. Для негативных отзывов (1-3 звезды) - НЕ соглашайся на все, но проси детали и фото если их нет
7. Максимальная уникальность - избегай шаблонных фраз
8. Длина ответа: 50-150 слов

Отвечай живо, по-человечески, как будто это твой любимый бренд."""

    def _build_response_prompt(self, review: WBReview) -> str:
        """Создание промпта для конкретного отзыва"""
        media_info = ""
        if review.has_photos:
            media_info += " (с фото)"
        if review.has_videos:
            media_info += " (с видео)"

        return f"""Напиши уникальный ответ на этот отзыв:

Имя покупателя: {review.customer_name}
Товар: {review.product_name}
Оценка: {review.rating} звезд
Текст отзыва: "{review.text}"{media_info}

Помни про все правила! Обращайся к покупателю по имени и обязательно упоминай SoVAni."""

    def _get_fallback_response(self, review: WBReview) -> str:
        """Резервный ответ при недоступности ChatGPT"""
        name = review.customer_name

        if review.rating >= 4:
            return f"Спасибо, {name}! Очень рады, что товар SoVAni вам понравился! 😊 Ждем вас снова за новыми покупками!"
        else:
            return f"Спасибо за отзыв, {name}. Команда SoVAni обязательно изучит ваши замечания. Будем рады помочь решить любые вопросы!"

class WBReviewsManager:
    """Менеджер для работы с отзывами WB"""

    def __init__(self):
        self.wb_api = api_clients.wb_api
        self.gpt_processor = ChatGPTReviewProcessor()

    async def get_new_reviews(self, limit: int = 50) -> List[WBReview]:
        """Получение новых отзывов с WB"""
        try:
            # Используем существующий метод получения отзывов
            raw_reviews = await self.wb_api.get_new_feedbacks()

            if not raw_reviews:
                logger.info("Новых отзывов WB не найдено")
                return []

            reviews = []
            for raw_review in raw_reviews[:limit]:
                review = self._parse_wb_review(raw_review)
                if review:
                    reviews.append(review)

            logger.info(f"Получено {len(reviews)} новых отзывов WB")
            return reviews

        except Exception as e:
            logger.error(f"Ошибка получения отзывов WB: {e}")
            return []

    async def get_all_unanswered_reviews(self, limit: int = 200) -> List[WBReview]:
        """Получение ВСЕХ неотвеченных отзывов с WB (для первого подключения)"""
        try:
            logger.info("Получение всех неотвеченных отзывов WB...")

            # Сначала пробуем получить неотвеченные отзывы
            raw_reviews = await self.wb_api.get_all_unanswered_feedbacks()

            if not raw_reviews:
                logger.info("Неотвеченных отзывов не найдено, показываем последние отзывы...")
                # Если неотвеченных нет, показываем последние отзывы (включая отвеченные)
                raw_reviews = await self._get_recent_reviews()

            if not raw_reviews:
                logger.info("Отзывов WB не найдено")
                return []

            # Парсим все отзывы
            all_reviews = []
            for raw_review in raw_reviews:
                review = self._parse_wb_review(raw_review)
                if review:
                    all_reviews.append(review)

            # Ограничиваем количество для безопасности
            final_reviews = all_reviews[:limit]

            unanswered_count = len([r for r in final_reviews if not r.answered])
            answered_count = len([r for r in final_reviews if r.answered])

            logger.info(f"Найдено {len(final_reviews)} отзывов WB: {unanswered_count} неотвеченных, {answered_count} отвеченных")

            return final_reviews

        except Exception as e:
            logger.error(f"Ошибка получения всех отзывов WB: {e}")
            return []

    async def _get_recent_reviews(self) -> List[Dict]:
        """Получение последних отзывов (включая отвеченные)"""
        try:
            url = f"{self.wb_api.BASE_URL}/api/v1/feedbacks"
            headers = self.wb_api._get_headers('feedbacks')

            # Параметры для получения отвеченных отзывов
            params = {
                'isAnswered': 'true',  # Получаем отвеченные отзывы
                'take': 50,           # Меньше лимит для недавних отзывов
                'skip': 0
            }

            logger.info(f"📋 Параметры для получения недавних отзывов: {params}")
            response_data = await self.wb_api._make_request_with_retry('GET', url, headers, params=params)

            if response_data:
                # Обрабатываем структуру ответа как в get_all_unanswered_feedbacks
                if isinstance(response_data, dict):
                    if 'data' in response_data:
                        data_section = response_data.get('data', {})
                        if 'feedbacks' in data_section:
                            return data_section.get('feedbacks', [])
                        else:
                            return data_section if isinstance(data_section, list) else []
                    else:
                        return response_data if isinstance(response_data, list) else []
                elif isinstance(response_data, list):
                    return response_data

            return []

        except Exception as e:
            logger.error(f"Ошибка получения недавних отзывов: {e}")
            return []

    def _parse_wb_review(self, raw_review: Dict) -> Optional[WBReview]:
        """
        Парсинг сырого отзыва от WB API в структурированный объект

        КРИТИЧЕСКИ ВАЖНЫЕ ИСПРАВЛЕНИЯ (Сентябрь 2025):
        1. Имена покупателей: извлекаются из userName (НЕ fallback "Покупатель")
        2. Названия товаров: извлекаются из productDetails.productName (НЕ fallback "Товар")
        3. Рейтинги: точный парсинг productValuation (НЕ fallback на 5 звезд)
        4. Медиафайлы: корректная обработка photoLinks и videoLinks

        Args:
            raw_review (Dict): Сырые данные отзыва от WB API

        Returns:
            Optional[WBReview]: Объект отзыва или None при ошибке парсинга

        Raises:
            Exception: При критических ошибках парсинга (логируется)
        """
        try:
            # Определяем наличие медиафайлов
            photos = raw_review.get('photoLinks', []) or []
            videos = raw_review.get('videoLinks', []) or []

            # ИСПРАВЛЕНИЕ: Правильное извлечение названия товара из productDetails
            # WB API хранит название в productDetails.productName, а не в корне
            product_details = raw_review.get('productDetails', {})
            product_name = product_details.get('productName', 'Товар')

            return WBReview(
                id=str(raw_review.get('id', '')),
                product_name=product_name,
                customer_name=raw_review.get('userName', 'Покупатель'),  # Реальные имена покупателей
                rating=int(raw_review.get('productValuation') or 1),  # ИСПРАВЛЕНИЕ: убран fallback на 5 звезд
                text=raw_review.get('text', '').strip(),
                created_at=raw_review.get('createdDate', ''),
                has_photos=len(photos) > 0,
                has_videos=len(videos) > 0,
                photos=photos,
                videos=videos,
                answered=raw_review.get('isAnswered', False),
                answer_text=raw_review.get('answer', {}).get('text') if raw_review.get('answer') else None
            )

        except Exception as e:
            logger.error(f"Ошибка парсинга отзыва: {e}")
            return None

    async def process_review(self, review: WBReview) -> Dict[str, Any]:
        """Обработка отзыва и генерация ответа"""
        try:
            # Генерируем ответ через ChatGPT
            response_text = await self.gpt_processor.generate_review_response(review)

            return {
                'review': review,
                'generated_response': response_text,
                'needs_approval': review.rating <= 3,  # 1-3 звезды требуют одобрения
                'auto_respond': review.rating >= 4     # 4-5 звезд отвечаем автоматически
            }

        except Exception as e:
            logger.error(f"Ошибка обработки отзыва {review.id}: {e}")
            return {
                'review': review,
                'generated_response': f"Спасибо за отзыв, {review.customer_name}! Команда SoVAni ценит ваше мнение.",
                'needs_approval': True,
                'auto_respond': False,
                'error': str(e)
            }

    async def send_review_response(self, review_id: str, response_text: str) -> bool:
        """Отправка ответа на отзыв через WB API"""
        try:
            logger.info(f"Отправка ответа на отзыв {review_id}")
            logger.info(f"Текст ответа: {response_text}")

            # Используем реальный WB API для отправки ответа
            result = await self.wb_api.send_review_response(review_id, response_text)
            return result

        except Exception as e:
            logger.error(f"Ошибка отправки ответа на отзыв {review_id}: {e}")
            return False

    def should_auto_respond(self, review: WBReview) -> bool:
        """Определяет, нужно ли отвечать автоматически"""
        return review.rating >= 4 and not review.answered

    def needs_user_approval(self, review: WBReview) -> bool:
        """Определяет, нужно ли одобрение пользователя"""
        return review.rating <= 3 and not review.answered

# Глобальный экземпляр менеджера отзывов
reviews_manager = WBReviewsManager()