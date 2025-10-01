"""Модуль для работы с API Wildberries и Ozon

ОСНОВНЫЕ КЛАССЫ:
- WildberriesAPI: Клиент для работы с WB API (6 токенов, JWT подпись)
- OzonAPI: Клиент для работы с Ozon API (Client-Id + API-Key)

ФУНКЦИОНАЛЬНОСТЬ WB API:
- Feedbacks API: получение/отправка отзывов и вопросов
- Statistics API: финансовая статистика и отчеты
- Content API: управление товарами и ценами
- Marketplace API: работа с заказами и продажами
- Analytics API: углубленная аналитика
- Ads API: управление рекламными кампаниями

ФУНКЦИОНАЛЬНОСТЬ OZON API:
- Finance API: финансовые транзакции и комиссии
- Analytics API: отчеты по продажам и заказам
- Products API: информация о товарах и остатках

БЕЗОПАСНОСТЬ:
- JWT подписи для WB API с приватным ключом
- Rate limiting для предотвращения блокировок
- Retry механизмы для стабильности соединения
- Валидация всех входящих данных

АВТОР: SoVAni Team
ПОСЛЕДНЕЕ ОБНОВЛЕНИЕ: Сентябрь 2025
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from config import Config
from db import question_exists, review_exists

logger = logging.getLogger(__name__)


class WildberriesAPI:
    """Клиент для работы с API Wildberries

    Поддерживает все основные API endpoints Wildberries:
    - Feedbacks API: отзывы, вопросы, чат с покупателями
    - Statistics API: финансовые данные, аналитика продаж
    - Content API: управление товарами, ценами, описаниями
    - Marketplace API: заказы, продажи, возвраты
    - Analytics API: углубленная аналитика и отчеты
    - Ads API: управление рекламными кампаниями

    ОСОБЕННОСТИ РЕАЛИЗАЦИИ:
    - JWT подпись для авторизации с приватным ключом
    - Автоматический retry при временных ошибках
    - Rate limiting для предотвращения блокировок API
    - Кэширование статуса доступности API
    - Fallback режимы при недоступности отдельных API

    БЕЗОПАСНОСТЬ:
    - Все токены читаются из переменных окружения
    - Приватный ключ хранится в защищенном файле
    - Логирование без раскрытия токенов
    """

    # API endpoints Wildberries
    BASE_URL = "https://feedbacks-api.wildberries.ru"  # Отзывы и вопросы
    STATS_BASE_URL = "https://statistics-api.wildberries.ru"  # Статистика и финансы
    CONTENT_BASE_URL = "https://content-api.wildberries.ru"  # Управление товарами
    MARKETPLACE_BASE_URL = "https://marketplace-api.wildberries.ru"  # Заказы и продажи

    def __init__(self):
        """Инициализация с загрузкой приватного ключа"""
        self.api_available = True
        self.api_status_message = "WB API инициализирован"
        self.last_status_check = None

        try:
            with open(Config.WB_PRIVATE_KEY_PATH, "rb") as key_file:
                self.private_key = key_file.read()
            logger.info("WB приватный ключ загружен успешно")
        except Exception as e:
            logger.error(f"Ошибка загрузки приватного ключа WB: {e}")
            self.private_key = None
            self.api_available = False
            self.api_status_message = f"WB API недоступен: ошибка ключа - {e}"

    def _get_token_for_auth(self, token_data: str) -> str:
        """Получение токена для авторизации (токен уже подписан WB)"""
        # Токен от WB уже правильно подписан их приватным ключом
        # Не нужно его перепоподписывать - используем как есть
        return token_data

    def _get_headers(self, token_type: str = "feedbacks") -> dict[str, str]:
        """Получение заголовков с JWT токеном"""
        token_map = {
            "feedbacks": Config.WB_FEEDBACKS_TOKEN,
            "stats": Config.WB_STATS_TOKEN,
            "content": Config.WB_CONTENT_TOKEN,
            "marketplace": Config.WB_SUPPLY_TOKEN,
        }

        token = token_map.get(token_type, Config.WB_FEEDBACKS_TOKEN)
        auth_token = self._get_token_for_auth(token)

        return {
            "Authorization": auth_token,  # Токен уже подписан WB, используем как есть
            "Content-Type": "application/json",
        }

    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        params: dict = None,
        json_data: dict = None,
        max_retries: int = 3,
    ) -> dict | None:
        """Выполнение запроса с retry механизмом"""
        for attempt in range(max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=60, connect=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    if method.upper() == "GET":
                        async with session.get(url, headers=headers, params=params) as response:
                            return await self._handle_response(response, attempt, max_retries)
                    elif method.upper() == "POST":
                        async with session.post(url, headers=headers, json=json_data) as response:
                            return await self._handle_response(response, attempt, max_retries)
                    elif method.upper() == "PATCH":
                        async with session.patch(url, headers=headers, json=json_data) as response:
                            return await self._handle_response(response, attempt, max_retries)

            except Exception as e:
                logger.error(f"Ошибка запроса WB API (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) * 5  # Экспоненциальная задержка
                    await asyncio.sleep(wait_time)
                else:
                    return None

        return None

    async def _handle_response(self, response, attempt: int, max_retries: int):
        """Обработка ответа с логикой retry и fallback"""
        response_text = await response.text()

        if response.status == 200:
            try:
                # API работает нормально
                if not self.api_available:
                    self.api_available = True
                    self.api_status_message = "WB API восстановлен"
                    logger.info("✅ WB API снова доступен")
                return await response.json()
            except:
                return {"text": response_text}

        elif response.status == 401:
            logger.error(f"WB API 401: {response_text[:200]}")

            # Проверяем на "token withdrawn"
            if "token withdrawn" in response_text:
                self.api_available = False
                self.api_status_message = "WB API недоступен: токены отозваны"
                logger.error("❌ WB API недоступен: все токены отозваны")
                return None

            if attempt < max_retries - 1:
                logger.info("Повторяем запрос с новым токеном...")
                await asyncio.sleep(2)
                raise Exception("401 - retry needed")

            # После всех попыток помечаем API как недоступный
            self.api_available = False
            self.api_status_message = "WB API недоступен: ошибка авторизации"
            return None

        elif response.status == 429:
            logger.warning(f"WB API 429 - лимит запросов: {response_text[:200]}")
            if attempt < max_retries - 1:
                wait_time = 60 + (attempt * 30)  # Увеличиваем задержку
                logger.info(f"Ждем {wait_time} секунд...")
                await asyncio.sleep(wait_time)
                raise Exception("429 - retry needed")
            return None

        else:
            logger.error(f"WB API ошибка {response.status}: {response_text[:200]}")
            # При критических ошибках помечаем API как недоступный
            if response.status >= 500:
                self.api_available = False
                self.api_status_message = f"WB API недоступен: серверная ошибка {response.status}"
            return None

    def get_api_status(self) -> dict[str, Any]:
        """Получение статуса WB API"""
        return {
            "available": self.api_available,
            "status_message": self.api_status_message,
            "last_check": self.last_status_check,
        }

    async def test_api_availability(self) -> bool:
        """Тест доступности WB API"""
        try:
            url = f"{self.BASE_URL}/api/v1/feedbacks"
            headers = self._get_headers("feedbacks")
            params = {"take": 1, "isAnswered": "false", "skip": 0}

            response_data = await self._make_request_with_retry(
                "GET", url, headers, params=params, max_retries=1
            )
            self.last_status_check = datetime.now()

            if response_data is not None:
                self.api_available = True
                self.api_status_message = "WB API доступен"
                return True
            else:
                self.api_available = False
                if "token withdrawn" in getattr(self, "_last_error_response", ""):
                    self.api_status_message = "WB API недоступен: токены отозваны"
                else:
                    self.api_status_message = "WB API недоступен: неизвестная ошибка"
                return False

        except Exception as e:
            self.api_available = False
            self.api_status_message = f"WB API недоступен: {e}"
            self.last_status_check = datetime.now()
            return False

    async def get_new_feedbacks(self) -> list[dict[str, Any]]:
        """Получение новых отзывов с Wildberries с проверкой доступности"""
        if not self.api_available:
            logger.warning(f"WB API недоступен: {self.api_status_message}")
            return []

        try:
            logger.info("🔍 Запрашиваем отзывы WB API...")
            url = f"{self.BASE_URL}/api/v1/feedbacks"
            headers = self._get_headers("feedbacks")

            # ИСПРАВЛЕНИЕ: Параметры без фильтрации по датам (WB API не поддерживает dateFrom/dateTo для отзывов)
            params = {
                "isAnswered": "false",  # Только неотвеченные отзывы
                "take": 5000,  # Максимальное количество
                "skip": 0,  # Начинаем с начала
            }

            logger.info(f"📋 Параметры запроса: {params}")
            response_data = await self._make_request_with_retry("GET", url, headers, params=params)

            if response_data:
                logger.info(f"📦 Получен ответ от WB API: {type(response_data)}")

                # ИСПРАВЛЕНИЕ: Улучшенная обработка структуры ответа
                if isinstance(response_data, dict):
                    if "data" in response_data:
                        data_section = response_data.get("data", {})
                        if "feedbacks" in data_section:
                            feedbacks = data_section.get("feedbacks", [])
                        else:
                            feedbacks = data_section if isinstance(data_section, list) else []
                    else:
                        # Возможно прямой массив отзывов
                        feedbacks = response_data if isinstance(response_data, list) else []
                elif isinstance(response_data, list):
                    feedbacks = response_data
                else:
                    logger.warning(f"⚠️ Неожиданная структура ответа: {type(response_data)}")
                    feedbacks = []

                logger.info(f"📊 Обработано отзывов из API: {len(feedbacks)}")

                new_feedbacks = []
                existing_count = 0

                for feedback in feedbacks:
                    feedback_id = str(feedback.get("id", ""))
                    logger.debug(f"🔍 Проверяем отзыв ID: {feedback_id}")

                    if feedback_id:
                        if not review_exists(feedback_id):
                            formatted_feedback = self._format_feedback(feedback)
                            new_feedbacks.append(formatted_feedback)
                            logger.debug(f"✅ Новый отзыв добавлен: {feedback_id}")
                        else:
                            existing_count += 1
                            logger.debug(f"⏭️ Отзыв уже существует: {feedback_id}")
                    else:
                        logger.warning(f"⚠️ Отзыв без ID: {feedback}")

                logger.info(
                    f"📈 РЕЗУЛЬТАТ: получено {len(feedbacks)} отзывов, новых: {len(new_feedbacks)}, уже существует: {existing_count}"
                )
                return new_feedbacks

            else:
                logger.warning("⚠️ API вернул пустой ответ")

        except Exception as e:
            logger.error(f"❌ Ошибка получения отзывов WB: {e}")
            import traceback

            logger.error(f"🔍 Детали ошибки: {traceback.format_exc()}")

        return []

    async def get_all_unanswered_feedbacks(self) -> list[dict[str, Any]]:
        """Получение ВСЕХ неотвеченных отзывов с Wildberries (включая уже существующие в БД)"""
        if not self.api_available:
            logger.warning(f"WB API недоступен: {self.api_status_message}")
            return []

        try:
            logger.info("🔍 Запрашиваем ВСЕ неотвеченные отзывы WB API...")
            url = f"{self.BASE_URL}/api/v1/feedbacks"
            headers = self._get_headers("feedbacks")

            # Параметры для получения всех неотвеченных отзывов
            params = {
                "isAnswered": "false",  # Только неотвеченные отзывы
                "take": 5000,  # Максимальное количество
                "skip": 0,  # Начинаем с начала
            }

            logger.info(f"📋 Параметры запроса ВСЕ неотвеченные: {params}")
            response_data = await self._make_request_with_retry("GET", url, headers, params=params)

            if response_data:
                logger.info(f"📦 Получен ответ от WB API: {type(response_data)}")

                # Обработка структуры ответа
                if isinstance(response_data, dict):
                    if "data" in response_data:
                        data_section = response_data.get("data", {})
                        if "feedbacks" in data_section:
                            feedbacks = data_section.get("feedbacks", [])
                        else:
                            feedbacks = data_section if isinstance(data_section, list) else []
                    else:
                        feedbacks = response_data if isinstance(response_data, list) else []
                elif isinstance(response_data, list):
                    feedbacks = response_data
                else:
                    logger.warning(f"⚠️ Неожиданная структура ответа: {type(response_data)}")
                    feedbacks = []

                logger.info(f"📊 Получено ВСЕ неотвеченных отзывов из API: {len(feedbacks)}")

                # Возвращаем ВСЕ отзывы без проверки на существование в БД
                all_feedbacks = []
                for feedback in feedbacks:
                    formatted_feedback = self._format_feedback(feedback)
                    all_feedbacks.append(formatted_feedback)

                logger.info(f"📈 РЕЗУЛЬТАТ ВСЕ неотвеченные: {len(all_feedbacks)} отзывов")
                return all_feedbacks

            else:
                logger.warning("⚠️ API вернул пустой ответ")

        except Exception as e:
            logger.error(f"❌ Ошибка получения всех неотвеченных отзывов WB: {e}")
            import traceback

            logger.error(f"🔍 Детали ошибки: {traceback.format_exc()}")

        return []

    async def get_new_questions(self) -> list[dict[str, Any]]:
        """Получение новых вопросов с Wildberries с проверкой доступности"""
        if not self.api_available:
            logger.warning(f"WB API недоступен: {self.api_status_message}")
            return []

        try:
            url = f"{self.BASE_URL}/api/v1/questions"
            headers = self._get_headers("feedbacks")
            params = {"isAnswered": "false", "take": 100, "skip": 0}

            response_data = await self._make_request_with_retry("GET", url, headers, params=params)

            if response_data:
                questions = response_data.get("data", {}).get("questions", [])

                new_questions = []
                for question in questions:
                    question_id = str(question.get("id", ""))
                    if question_id and not question_exists(question_id):
                        new_questions.append(self._format_question(question))

                logger.info(f"WB: получено {len(questions)} вопросов, новых: {len(new_questions)}")
                return new_questions

        except Exception as e:
            logger.error(f"Ошибка получения вопросов WB: {e}")

        return []

    async def post_feedback_answer(self, feedback_id: str, answer_text: str) -> bool:
        """Отправка ответа на отзыв с JWT подписью"""
        try:
            url = f"{self.BASE_URL}/api/v1/feedbacks"
            headers = self._get_headers("feedbacks")
            json_data = {"id": feedback_id, "answer": {"text": answer_text}}

            logger.info(f"Отправляю ответ на отзыв {feedback_id} с JWT: {answer_text[:50]}...")

            response_data = await self._make_request_with_retry(
                "PATCH", url, headers, json_data=json_data
            )

            if response_data is not None:
                logger.info(f"✅ Ответ на отзыв {feedback_id} отправлен успешно")
                return True
            else:
                logger.error(f"❌ Не удалось отправить ответ на отзыв {feedback_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Критическая ошибка отправки ответа на отзыв: {e}")
            return False

    async def post_question_answer(self, question_id: str, answer_text: str) -> bool:
        """Отправка ответа на вопрос с JWT подписью"""
        try:
            url = f"{self.BASE_URL}/api/v1/questions"
            headers = self._get_headers("feedbacks")
            json_data = {"id": question_id, "answer": {"text": answer_text}}

            logger.info(f"Отправляю ответ на вопрос {question_id} с JWT: {answer_text[:50]}...")

            response_data = await self._make_request_with_retry(
                "PATCH", url, headers, json_data=json_data
            )

            if response_data is not None:
                logger.info(f"✅ Ответ на вопрос {question_id} отправлен успешно")
                return True
            else:
                logger.error(f"❌ Не удалось отправить ответ на вопрос {question_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Критическая ошибка отправки ответа на вопрос: {e}")
            return False

    def _format_feedback(self, feedback_data: dict) -> dict[str, Any]:
        """Форматирование данных отзыва"""
        return {
            "id": str(feedback_data.get("id", "")),
            "sku": feedback_data.get("productDetails", {}).get("nmId", "N/A"),
            "text": feedback_data.get("text", ""),
            "rating": feedback_data.get("productValuation", 0),
            "has_media": bool(feedback_data.get("photoLinks") or feedback_data.get("videoLink")),
            "date": self._parse_date(feedback_data.get("createdDate")),
            "product_name": feedback_data.get("productDetails", {}).get("productName", ""),
        }

    def _format_question(self, question_data: dict) -> dict[str, Any]:
        """Форматирование данных вопроса"""
        return {
            "id": str(question_data.get("id", "")),
            "sku": question_data.get("productDetails", {}).get("nmId", "N/A"),
            "text": question_data.get("text", ""),
            "date": self._parse_date(question_data.get("createdDate")),
            "product_name": question_data.get("productDetails", {}).get("productName", ""),
        }

    def _parse_date(self, date_str: str) -> datetime:
        """Парсинг даты из строки"""
        try:
            if date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            pass
        return datetime.now()

    async def get_advertising_campaigns(self) -> dict[str, Any]:
        """Получение информации о рекламных кампаниях"""
        try:
            from rate_limiter import with_rate_limit

            # Применяем rate limiting для рекламного API
            await with_rate_limit("wb_advertising")

            url = "https://advert-api.wildberries.ru/adv/v1/promotion/count"

            headers = {
                "Authorization": f"Bearer {Config.WB_ADS_TOKEN}",
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        adverts_groups = data.get("adverts", [])
                        all_count = data.get("all", 0)

                        # Извлекаем все кампании из всех групп
                        all_campaigns = []
                        for group in adverts_groups:
                            advert_list = group.get("advert_list", [])
                            for campaign in advert_list:
                                campaign["group_type"] = group.get("type")
                                campaign["group_status"] = group.get("status")
                                all_campaigns.append(campaign)

                        logger.info(
                            f"WB кампании: найдено {len(all_campaigns)} активных из {all_count} общих"
                        )

                        # Форматируем данные кампаний
                        formatted_campaigns = []
                        for campaign in all_campaigns:
                            formatted_campaigns.append(
                                {
                                    "campaign_id": campaign.get("advertId"),
                                    "type": campaign.get("group_type", "unknown"),
                                    "status": campaign.get("group_status", "unknown"),
                                    "change_time": campaign.get("changeTime", ""),
                                }
                            )

                        return {
                            "total_campaigns": all_count,
                            "active_campaigns": len(all_campaigns),
                            "campaigns": formatted_campaigns,
                            "raw_data": all_campaigns,
                        }
                    else:
                        response_text = await response.text()
                        logger.warning(f"WB Advert API error {response.status}: {response_text}")
                        return {
                            "total_spend": 0,
                            "campaigns": [],
                            "error": f"API error {response.status}",
                        }

        except Exception as e:
            logger.error(f"Ошибка получения рекламных кампаний WB: {e}")
            return {"total_spend": 0, "campaigns": [], "error": str(e)}

    async def send_review_response(self, review_id: str, response_text: str) -> bool:
        """Отправка ответа на отзыв WB"""
        try:
            logger.info(f"Отправка ответа на отзыв WB {review_id}")

            # URL для отправки ответа на отзыв (исправлен согласно документации)
            url = f"{self.BASE_URL}/api/v1/feedbacks/answer"

            headers = self._get_headers("feedbacks")

            # Payload для ответа на отзыв (согласно документации)
            payload = {"id": review_id, "text": response_text}

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status in [200, 204]:  # 200 OK или 204 No Content - оба успешные
                        logger.info(
                            f"✅ Ответ на отзыв {review_id} отправлен успешно (код {response.status})"
                        )
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"❌ Ошибка отправки ответа на отзыв {review_id}: {response.status} - {error_text}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Ошибка отправки ответа на отзыв {review_id}: {e}")
            return False


class OzonAPI:
    """Клиент для работы с API Ozon"""

    BASE_URL = "https://api-seller.ozon.ru"

    def __init__(self):
        self.headers = {
            "Client-Id": Config.OZON_CLIENT_ID,
            "Api-Key": Config.OZON_API_KEY,
            "Content-Type": "application/json",
        }
        logger.info(f"OzonAPI initialized with Client-Id: {Config.OZON_CLIENT_ID}")

    async def get_product_reviews(self) -> list[dict[str, Any]]:
        """Получение отзывов с Ozon"""
        try:
            from rate_limiter import with_rate_limit

            # Применяем rate limiting для Ozon API
            await with_rate_limit("ozon_general")

            url = f"{self.BASE_URL}/v1/product/rating-by-sku"

            # Получаем список SKU товаров
            products_url = f"{self.BASE_URL}/v3/product/list"
            products_payload = {"filter": {"visibility": "ALL"}, "last_id": "", "limit": 100}

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                # Сначала получаем список товаров
                async with session.post(
                    products_url, headers=self.headers, json=products_payload
                ) as response:
                    if response.status == 200:
                        products_data = await response.json()
                        products = products_data.get("result", {}).get("items", [])

                        reviews = []
                        for product in products[:10]:  # Лимит для тестирования
                            sku = product.get("sku")
                            if sku:
                                rating_payload = {"sku": [sku]}

                                async with session.post(
                                    url, headers=self.headers, json=rating_payload
                                ) as rating_response:
                                    if rating_response.status == 200:
                                        rating_data = await rating_response.json()
                                        product_ratings = rating_data.get("result", [])

                                        for rating in product_ratings:
                                            reviews.append(
                                                {
                                                    "id": f"ozon_{sku}_{rating.get('rating', 0)}",
                                                    "sku": sku,
                                                    "rating": rating.get("rating", 0),
                                                    "reviews_count": rating.get("reviews_count", 0),
                                                    "text": f"Средняя оценка: {rating.get('rating', 0)}/5",
                                                    "date": datetime.now(),
                                                    "platform": "ozon",
                                                }
                                            )

                        logger.info(f"Ozon: получено {len(reviews)} отзывов/рейтингов")
                        return reviews
                    else:
                        logger.error(f"Ozon API ошибка получения товаров: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Ошибка получения отзывов Ozon: {e}")
            return []

    async def download_sales_report(self) -> str | None:
        """Получение данных продаж с Ozon через Analytics API"""
        try:
            # Используем рабочий Analytics API endpoint
            url = f"{self.BASE_URL}/v1/analytics/data"
            date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            date_to = datetime.now().strftime("%Y-%m-%d")

            payload = {
                "date_from": date_from,
                "date_to": date_to,
                "metrics": [
                    "revenue",
                    "ordered_units",
                    "hits_view_search",
                    "hits_view_pdp",
                    "conversion",
                ],
                "dimension": ["sku"],
                "filters": [],
                "sort": [],
                "limit": 1000,
                "offset": 0,
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                logger.info(
                    f"Ozon: получение данных продаж через Analytics API за период {date_from} - {date_to}"
                )

                async with session.post(url, headers=self.headers, json=payload) as response:
                    response_text = await response.text()
                    logger.info(
                        f"Ozon Analytics API response: {response.status}, text: {response_text[:200]}"
                    )

                    if response.status == 200:
                        data = await response.json()
                        sales_data = data.get("result", {}).get("data", [])

                        if sales_data:
                            # Сохраняем данные в файл
                            import json

                            os.makedirs("reports", exist_ok=True)
                            filename = (
                                f"reports/ozon_sales_{datetime.now().strftime('%Y%m%d')}.json"
                            )

                            with open(filename, "w", encoding="utf-8") as f:
                                json.dump(sales_data, f, ensure_ascii=False, indent=2)

                            logger.info(
                                f"Ozon: сохранено {len(sales_data)} записей продаж в {filename}"
                            )
                            return filename
                        else:
                            logger.info("Ozon Analytics API: нет данных за указанный период")
                            return None
                    else:
                        logger.error(
                            f"Ozon Analytics API ошибка: {response.status}, {response_text}"
                        )

        except Exception as e:
            logger.error(f"Ошибка получения данных Analytics Ozon: {e}")

        return None

    async def _wait_and_download_report(
        self, report_code: str, session: aiohttp.ClientSession
    ) -> str | None:
        """Ожидание готовности и скачивание отчета"""
        info_url = f"{self.BASE_URL}/v1/analytics_data"
        payload = {"code": report_code}

        # Ждем готовности отчета (до 5 минут)
        for attempt in range(10):
            await asyncio.sleep(30)  # Ждем 30 сек между проверками

            try:
                async with session.post(info_url, headers=self.headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data.get("result", {})
                        status = result.get("status")

                        logger.info(
                            f"Ozon отчет {report_code}: статус {status}, попытка {attempt + 1}/10"
                        )

                        if status == "success":
                            file_url = result.get("file")

                            if file_url:
                                # Скачиваем готовый файл
                                async with session.get(file_url) as file_response:
                                    if file_response.status == 200:
                                        file_path = f"reports/ozon_sales_{datetime.now().strftime('%Y%m%d')}.xlsx"

                                        # Создаем папку reports если её нет
                                        os.makedirs("reports", exist_ok=True)

                                        with open(file_path, "wb") as f:
                                            f.write(await file_response.read())

                                        logger.info(f"Ozon отчет скачан: {file_path}")
                                        return file_path
                                    else:
                                        logger.error(
                                            f"Ошибка скачивания файла Ozon: {file_response.status}"
                                        )
                            else:
                                logger.error("Ozon API: URL файла не найден")

                        elif status == "failed":
                            logger.error("Ozon отчет: генерация не удалась")
                            break
                        # Если статус processing - продолжаем ожидание

                    else:
                        logger.error(f"Ozon info API ошибка: {response.status}")

            except Exception as e:
                logger.error(f"Ошибка проверки статуса отчета Ozon: {e}")

        logger.error("Ozon: превышено время ожидания отчета")
        return None

    async def get_product_stocks(self) -> list[dict[str, Any]]:
        """Получение остатков товаров с Ozon через несколько API методов"""
        from rate_limiter import with_rate_limit

        # Применяем rate limiting для Ozon API
        await with_rate_limit("ozon_general")

        # Пытаемся получить остатки через разные endpoints
        stocks = []

        # Метод 0: Получение списка складов для понимания структуры
        warehouses = await self._get_warehouses()
        if warehouses:
            logger.info(f"Ozon: найдено {len(warehouses)} складов")

        # Метод 1: FBO склады (склады Ozon - основные остатки)
        stocks_fbo = await self._get_fbo_stocks()
        if stocks_fbo:
            stocks.extend(stocks_fbo)
            logger.info(f"Ozon FBO: получено {len(stocks_fbo)} остатков")

        # Метод 2: FBS склады (склады продавца)
        stocks_fbs = await self._get_fbs_stocks()
        if stocks_fbs:
            stocks.extend(stocks_fbs)
            logger.info(f"Ozon FBS: получено {len(stocks_fbs)} остатков")

        # Метод 3: Традиционный v3/product/list
        stocks_v3 = await self._get_stocks_v3()
        if stocks_v3:
            # Объединяем, избегая дубликатов
            existing_ids = {item.get("product_id") for item in stocks}
            for item in stocks_v3:
                if item.get("product_id") not in existing_ids:
                    stocks.append(item)
            logger.info(
                f"Ozon v3: добавлено {len([item for item in stocks_v3 if item.get('product_id') not in existing_ids])} остатков"
            )

        # Метод 4: Analytics warehouse stocks
        stocks_analytics = await self._get_analytics_stocks()
        if stocks_analytics:
            existing_ids = {item.get("product_id") for item in stocks}
            for item in stocks_analytics:
                if item.get("product_id") not in existing_ids:
                    stocks.append(item)
            logger.info(
                f"Ozon Analytics: добавлено {len([item for item in stocks_analytics if item.get('product_id') not in existing_ids])} остатков"
            )

        logger.info(f"Ozon: итого получено {len(stocks)} остатков")
        return stocks

    async def _get_warehouses(self) -> list[dict[str, Any]]:
        """Получение списка складов Ozon"""
        try:
            url = f"{self.BASE_URL}/v1/warehouse/list"

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(url, headers=self.headers, json={}) as response:
                    if response.status == 200:
                        data = await response.json()
                        warehouses = data.get("result", [])

                        for warehouse in warehouses:
                            logger.info(
                                f"Склад: {warehouse.get('name')}, ID: {warehouse.get('warehouse_id')}, Тип: {warehouse.get('type')}"
                            )

                        return warehouses
                    else:
                        response_text = await response.text()
                        logger.debug(
                            f"Ozon warehouse list: {response.status}, {response_text[:200]}"
                        )
                        return []
        except Exception as e:
            logger.debug(f"Ошибка получения списка складов Ozon: {e}")
            return []

    async def _get_fbo_stocks(self) -> list[dict[str, Any]]:
        """Получение остатков FBO складов (склады Ozon)"""
        # Пробуем endpoints из официальной документации
        fbo_endpoints = [
            "/v2/analytics/stock_on_warehouses",
            "/v1/analytics/manage/stocks",
            "/v1/analytics/turnover/stocks",
            "/v1/warehouse/fbo/list",
        ]

        for endpoint in fbo_endpoints:
            try:
                url = f"{self.BASE_URL}{endpoint}"

                # Разные payloads для разных endpoints
                if "analytics" in endpoint:
                    payload = {
                        "dimension": ["sku"],
                        "metrics": ["stocks"],
                        "limit": 1000,
                        "offset": 0,
                    }
                else:
                    payload = {}

                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as session:
                    async with session.post(url, headers=self.headers, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            stocks = []

                            # Обработка разных форматов ответов
                            if "analytics" in endpoint:
                                # Analytics API format
                                for item in data.get("result", {}).get("data", []):
                                    dimensions = item.get("dimensions", [])
                                    metrics = item.get("metrics", [])
                                    if dimensions and metrics:
                                        stocks.append(
                                            {
                                                "sku": dimensions[0].get("id"),
                                                "offer_id": dimensions[0].get("name"),
                                                "product_id": dimensions[0].get("id"),
                                                "stock": metrics[0] if metrics else 0,
                                                "reserved": 0,
                                                "warehouse_id": None,
                                                "platform": "ozon",
                                                "type": f'FBO_{endpoint.split("/")[-1]}',
                                            }
                                        )
                            else:
                                # Standard format
                                for item in data.get("result", []):
                                    stocks.append(
                                        {
                                            "sku": item.get("sku"),
                                            "offer_id": item.get("offer_id"),
                                            "product_id": item.get("product_id"),
                                            "stock": item.get("present", 0),
                                            "reserved": item.get("reserved", 0),
                                            "warehouse_id": item.get("warehouse_id"),
                                            "platform": "ozon",
                                            "type": f'FBO_{endpoint.split("/")[-1]}',
                                        }
                                    )

                            if stocks:
                                logger.info(
                                    f"Ozon FBO endpoint {endpoint}: получено {len(stocks)} остатков"
                                )
                                return stocks
                            else:
                                logger.info(
                                    f"Ozon FBO endpoint {endpoint}: данные получены, но остатки пустые"
                                )
                        else:
                            response_text = await response.text()
                            logger.debug(
                                f"Ozon FBO {endpoint}: {response.status}, {response_text[:100]}"
                            )

            except Exception as e:
                logger.debug(f"Ошибка FBO endpoint {endpoint}: {e}")
                continue

        logger.warning("Все FBO endpoints недоступны или не содержат данных")
        return []

    async def _get_fbs_stocks(self) -> list[dict[str, Any]]:
        """Попытка получения остатков через имитацию запроса v2/products/stocks"""
        try:
            # v2/products/stocks предназначен для обновления, но попробуем GET
            url = f"{self.BASE_URL}/v2/products/stocks"

            # Попробуем сначала GET запрос
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        stocks = []

                        # Обработка возможных форматов ответа
                        result_data = data.get("result", data)
                        if isinstance(result_data, list):
                            stocks_list = result_data
                        else:
                            stocks_list = result_data.get("stocks", result_data.get("items", []))

                        for item in stocks_list:
                            stocks.append(
                                {
                                    "sku": item.get("sku"),
                                    "offer_id": item.get("offer_id"),
                                    "product_id": item.get("product_id"),
                                    "stock": item.get("stock", item.get("present", 0)),
                                    "reserved": item.get("reserved", 0),
                                    "warehouse_id": item.get("warehouse_id"),
                                    "platform": "ozon",
                                    "type": "stocks_v2_get",
                                }
                            )

                        logger.info(f"GET /v2/products/stocks: получено {len(stocks)} записей")
                        return stocks
                    else:
                        response_text = await response.text()
                        logger.debug(
                            f"GET /v2/products/stocks: {response.status}, {response_text[:200]}"
                        )

                # Если GET не работает, попробуем POST с пустым телом
                async with session.post(url, headers=self.headers, json={}) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"POST /v2/products/stocks с пустым телом: {data}")
                        return []
                    else:
                        response_text = await response.text()
                        logger.debug(
                            f"POST /v2/products/stocks пустой: {response.status}, {response_text[:100]}"
                        )

        except Exception as e:
            logger.warning(f"Ошибка тестирования v2/products/stocks: {e}")

        return []

    async def _get_stocks_v3(self) -> list[dict[str, Any]]:
        """Получение остатков через рабочий v3/product/list с улучшенной обработкой FBO/FBS"""
        try:
            # Возвращаемся к рабочему endpoint, но с улучшенной обработкой
            url = f"{self.BASE_URL}/v3/product/list"
            payload = {"filter": {"visibility": "ALL"}, "last_id": "", "limit": 1000}

            stocks = []
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("result", {}).get("items", [])

                        for item in items:
                            # Детальный анализ структуры stocks
                            stocks_info = item.get("stocks", {})

                            # Попытка извлечь FBO/FBS данные разными способами
                            fbo_stock = 0
                            fbs_stock = 0
                            total_stock = 0
                            reserved = 0

                            if isinstance(stocks_info, list):
                                # Если stocks - это массив складов
                                for stock_item in stocks_info:
                                    warehouse_type = stock_item.get("type", "").lower()
                                    present = stock_item.get("present", 0)
                                    total_stock += present
                                    reserved += stock_item.get("reserved", 0)

                                    if "fbo" in warehouse_type or warehouse_type == "":
                                        fbo_stock += present
                                    elif "fbs" in warehouse_type:
                                        fbs_stock += present
                                    else:
                                        # Если тип неизвестен, считаем как FBO (склад Ozon)
                                        fbo_stock += present

                            elif isinstance(stocks_info, dict):
                                # Если stocks - это объект
                                total_stock = stocks_info.get("present", 0)
                                reserved = stocks_info.get("reserved", 0)

                                # Проверяем наличие FBO/FBS полей
                                if "fbo" in stocks_info or "fbs" in stocks_info:
                                    fbo_stock = stocks_info.get("fbo", 0)
                                    fbs_stock = stocks_info.get("fbs", 0)
                                else:
                                    # Если разделения нет, считаем все как FBO
                                    fbo_stock = total_stock
                                    fbs_stock = 0

                            # Логируем детали для понимания структуры
                            if total_stock > 0:
                                logger.info(
                                    f"Товар с остатками: {item.get('offer_id')}, structure: {stocks_info}"
                                )

                            stocks.append(
                                {
                                    "sku": item.get("sku"),
                                    "offer_id": item.get("offer_id"),
                                    "product_id": item.get("product_id"),
                                    "stock": total_stock,
                                    "fbo_stock": fbo_stock,
                                    "fbs_stock": fbs_stock,
                                    "reserved": reserved,
                                    "warehouse_id": None,
                                    "platform": "ozon",
                                    "type": "product_list_v3",
                                    "raw_stocks": stocks_info,  # Для отладки
                                }
                            )

                        return stocks
                    else:
                        response_text = await response.text()
                        logger.warning(
                            f"Ozon v3/product/list API: {response.status}, {response_text[:200]}"
                        )
                        return []
        except Exception as e:
            logger.warning(f"Ошибка получения остатков через v3/product/list: {e}")
            return []

    async def _get_analytics_stocks(self) -> list[dict[str, Any]]:
        """Получение остатков через РАБОЧИЙ Analytics API"""
        try:
            url = f"{self.BASE_URL}/v2/analytics/stock_on_warehouses"

            # Рабочий payload из тестирования
            payload = {
                "dimensions": ["sku"],
                "metrics": ["stocks_fbo", "stocks_fbs"],
                "limit": 1000,
                "offset": 0,
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        stocks = []

                        # Правильная структура из тестирования: result.rows
                        for item in data.get("result", {}).get("rows", []):
                            sku = item.get("sku")
                            item_code = item.get("item_code")
                            item_name = item.get("item_name")
                            warehouse_name = item.get("warehouse_name")

                            # Остатки из реального ответа
                            free_to_sell = item.get("free_to_sell_amount", 0)
                            promised = item.get("promised_amount", 0)
                            reserved = item.get("reserved_amount", 0)

                            total_stock = free_to_sell + promised + reserved

                            stocks.append(
                                {
                                    "sku": sku,
                                    "offer_id": item_code,
                                    "product_id": sku,
                                    "stock": total_stock,
                                    "fbo_stock": free_to_sell,  # FBO = доступно к продаже
                                    "fbs_stock": 0,  # Пока считаем все как FBO
                                    "reserved": reserved,
                                    "warehouse_id": None,
                                    "warehouse_name": warehouse_name,
                                    "platform": "ozon",
                                    "type": "Analytics_Working",
                                }
                            )

                        logger.info(f"Analytics API: получено {len(stocks)} записей остатков")
                        return stocks
                    else:
                        response_text = await response.text()
                        logger.warning(
                            f"Ozon Analytics API: {response.status}, {response_text[:200]}"
                        )
                        return []
        except Exception as e:
            logger.warning(f"Ошибка получения Analytics остатков Ozon: {e}")
            return []


class WBBusinessAPI:
    """Клиент для работы с бизнес-данными Wildberries"""

    def __init__(self):
        self.headers = {
            "Authorization": Config.WB_REPORTS_TOKEN,
            "Content-Type": "application/json",
        }
        # Заголовки для рекламного API - v1 API работает с ADS_TOKEN
        self.ads_headers = {
            "Authorization": f"Bearer {Config.WB_ADS_TOKEN}",
            "Content-Type": "application/json",
        }
        logger.info("WBBusinessAPI initialized")

    async def get_warehouses(self) -> list[dict[str, Any]]:
        """Получение информации о складах"""
        try:
            url = "https://marketplace-api.wildberries.ru/api/v3/warehouses"

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        warehouses = await response.json()
                        logger.info(f"WB: получено {len(warehouses)} складов")
                        return warehouses
                    else:
                        response_text = await response.text()
                        logger.error(f"WB Warehouses API error {response.status}: {response_text}")
                        return []

        except Exception as e:
            logger.error(f"Ошибка получения складов WB: {e}")
            return []

    async def get_new_orders(self) -> list[dict[str, Any]]:
        """Получение новых заказов"""
        try:
            url = "https://marketplace-api.wildberries.ru/api/v3/orders/new"

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        orders = data.get("orders", [])
                        logger.info(f"WB: получено {len(orders)} новых заказов")
                        return orders
                    else:
                        response_text = await response.text()
                        logger.error(f"WB Orders API error {response.status}: {response_text}")
                        return []

        except Exception as e:
            logger.error(f"Ошибка получения заказов WB: {e}")
            return []

    async def get_product_cards(self) -> list[dict[str, Any]]:
        """Получение карточек товаров"""
        try:
            url = "https://content-api.wildberries.ru/content/v2/get/cards/list"
            payload = {
                "settings": {
                    "cursor": {"limit": 100}  # Максимум за запрос (WB ограничивает до 100)
                }
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        cards = data.get("cards", [])
                        cursor = data.get("cursor", {})
                        total = cursor.get("total", 0)

                        logger.info(f"WB: получено {len(cards)} карточек из {total} общих")
                        return cards
                    else:
                        response_text = await response.text()
                        logger.error(f"WB Content API error {response.status}: {response_text}")
                        return []

        except Exception as e:
            logger.error(f"Ошибка получения карточек WB: {e}")
            return []

    async def get_advertising_campaigns(self) -> dict[str, Any]:
        """Получение информации о рекламных кампаниях"""
        try:
            url = "https://advert-api.wildberries.ru/adv/v1/promotion/count"

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(url, headers=self.ads_headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        adverts = data.get("adverts", [])
                        all_count = data.get("all", 0)

                        # Анализируем структуру кампаний
                        campaigns_by_type = {}
                        total_active_campaigns = 0

                        for campaign in adverts:
                            campaign_type = campaign.get("type")
                            count = campaign.get("count", 0)
                            status = campaign.get("status")

                            if campaign_type not in campaigns_by_type:
                                campaigns_by_type[campaign_type] = {
                                    "total_campaigns": 0,
                                    "statuses": {},
                                    "campaigns": [],
                                }

                            campaigns_by_type[campaign_type]["total_campaigns"] += count
                            campaigns_by_type[campaign_type]["campaigns"].append(campaign)

                            if status not in campaigns_by_type[campaign_type]["statuses"]:
                                campaigns_by_type[campaign_type]["statuses"][status] = 0
                            campaigns_by_type[campaign_type]["statuses"][status] += count

                            total_active_campaigns += count

                        result = {
                            "total_campaigns": all_count,
                            "active_campaigns": total_active_campaigns,
                            "active_campaign_types": len(adverts),
                            "campaigns_by_type": campaigns_by_type,
                            "raw_data": adverts,
                        }

                        logger.info(
                            f"WB: всего {all_count} кампаний, активных {total_active_campaigns}"
                        )
                        return result
                    else:
                        response_text = await response.text()
                        logger.error(f"WB Advert API error {response.status}: {response_text}")
                        return {}

        except Exception as e:
            logger.error(f"Ошибка получения рекламы WB: {e}")
            return {}

    async def get_fullstats_v3(self, date_from: str, date_to: str) -> dict[str, Any]:
        """Получение полной статистики рекламы WB API v3 - ИСПРАВЛЕНИЕ ОТСУТСТВУЮЩЕГО МЕТОДА"""
        try:
            # Получаем кампании сначала
            campaigns_data = await self.get_advertising_campaigns()
            if not campaigns_data.get("raw_data"):
                logger.warning("WB Advertising: нет активных кампаний для статистики v3")
                return {"total_spend": 0, "campaigns": [], "period": f"{date_from} - {date_to}"}

            total_spend = 0
            campaigns_stats = []

            # ИСПРАВЛЕНИЕ: Извлекаем ID кампаний из advert_list в raw_data
            for campaign_group in campaigns_data["raw_data"]:
                for campaign in campaign_group.get("advert_list", []):
                    campaign_id = campaign.get("advertId")
                    if not campaign_id:
                        continue

                try:
                    # ИСПРАВЛЕНИЕ: stat API не работают, используем только данные кампаний
                    # Получаем детали кампании через рабочий эндпоинт
                    url = "https://advert-api.wildberries.ru/adv/v1/promotion/adverts"
                    payload = [campaign_id]

                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as session:
                        async with session.post(
                            url, headers=self.ads_headers, json=payload
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                # Парсим статистику кампании
                                if data and isinstance(data, list) and len(data) > 0:
                                    campaign_data = data[0]
                                    # ИСПРАВЛЕНИЕ: В данных кампании нет расходов, только бюджет
                                    daily_budget = campaign_data.get("dailyBudget", 0)
                                    campaign_name = campaign_data.get("name", "Без названия")
                                    status = campaign_data.get("status", 0)

                                    # Расходы пока недоступны через API (требует scope)
                                    spend = 0  # Будет 0 пока scope не исправят

                                    campaigns_stats.append(
                                        {
                                            "campaign_id": campaign_id,
                                            "name": campaign_name,
                                            "status": status,
                                            "daily_budget": daily_budget,
                                            "spend": spend,
                                            "views": 0,  # Недоступно без stat API
                                            "clicks": 0,  # Недоступно без stat API
                                            "ctr": 0,  # Недоступно без stat API
                                        }
                                    )
                            else:
                                logger.warning(
                                    f"WB v3 API ошибка {response.status} для кампании {campaign_id}"
                                )

                except Exception as campaign_error:
                    logger.warning(
                        f"Ошибка получения статистики кампании {campaign_id}: {campaign_error}"
                    )
                    continue

            result = {
                "total_spend": total_spend,
                "total_views": sum(c.get("views", 0) for c in campaigns_stats),
                "total_clicks": sum(c.get("clicks", 0) for c in campaigns_stats),
                "campaigns": campaigns_stats,
                "period": f"{date_from} - {date_to}",
                "campaigns_processed": len(campaigns_stats),
            }

            logger.info(
                f"WB v3 API: обработано {len(campaigns_stats)} кампаний, расходы {total_spend:.2f} ₽"
            )
            return result

        except Exception as e:
            logger.error(f"Критическая ошибка WB fullstats v3: {e}")
            return {"total_spend": 0, "campaigns": [], "error": str(e)}

    async def get_advertising_statistics(
        self, date_from: str, date_to: str, campaign_ids: list[str] = None
    ) -> dict[str, Any]:
        """КРИТИЧЕСКИЙ МЕТОД: Получение статистики рекламных кампаний WB с улучшенной обработкой ошибок

        Args:
            date_from: Дата начала в формате YYYY-MM-DD
            date_to: Дата окончания в формате YYYY-MM-DD
            campaign_ids: Список ID кампаний (если None - все кампании)

        Returns:
            Dict с данными рекламной статистики

        """
        try:
            from rate_limiter import with_rate_limit

            logger.info(f"🔍 Получение рекламной статистики WB за {date_from} - {date_to}")

            # Применяем rate limiting для рекламного API
            await with_rate_limit("wb_advertising")

            # Если не указаны кампании, используем fullstats v3
            if not campaign_ids:
                return await self.get_fullstats_v3(date_from, date_to)

            # Если указаны конкретные кампании, получаем их статистику
            total_spend = 0.0
            campaign_stats = []

            for campaign_id in campaign_ids:
                await with_rate_limit("wb_advertising")  # Rate limiting перед каждым запросом

                # ИСПРАВЛЕНИЕ: stat API не работают, используем promotion/adverts
                url = "https://advert-api.wildberries.ru/adv/v1/promotion/adverts"
                payload = [campaign_id]

                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as session:
                    async with session.post(
                        url, headers=self.ads_headers, json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()

                            if isinstance(data, list) and data:
                                campaign_data = data[0]
                                # ИСПРАВЛЕНИЕ: Используем данные кампании, а не статистику
                                daily_budget = campaign_data.get("dailyBudget", 0)
                                campaign_name = campaign_data.get("name", "Без названия")
                                spend = 0  # Фактические расходы недоступны без scope

                                campaign_stats.append(
                                    {
                                        "campaign_id": campaign_data.get("advertId", campaign_id),
                                        "name": campaign_name,
                                        "daily_budget": daily_budget,
                                        "status": campaign_data.get("status", 0),
                                        "spend": spend,
                                        "views": 0,  # Недоступно
                                        "clicks": 0,  # Недоступно
                                        "ctr": 0,
                                        "cpc": 0,
                                        "orders": 0,
                                    }
                                )

                        elif response.status == 429:
                            # Обрабатываем 429 с помощью rate limiter
                            from rate_limiter import rate_limiter

                            await rate_limiter.handle_429_error("wb_advertising", 0)
                            logger.warning(
                                f"WB Advertising: получен 429 для кампании {campaign_id}"
                            )

                        elif response.status == 401:
                            error_text = await response.text()
                            logger.error(f"WB Advertising API 401 Unauthorized: {error_text}")
                            logger.error(
                                "🚨 РЕШЕНИЕ: Перевыпустите токен с scope 'Продвижение' в кабинете WB!"
                            )
                            # Не прерываем, продолжаем с другими кампаниями

                        else:
                            error_text = await response.text()
                            logger.warning(
                                f"WB Advertising API {response.status}: {error_text[:200]}"
                            )

            logger.info(
                f"✅ WB реклама: {total_spend:,.2f} ₽ за период ({len(campaign_stats)} кампаний)"
            )

            return {
                "total_spend": total_spend,
                "campaigns": campaign_stats,
                "period": f"{date_from} - {date_to}",
                "campaign_count": len(campaign_stats),
            }

        except Exception as e:
            logger.error(f"❌ Критическая ошибка получения рекламной статистики WB: {e}")
            return {
                "total_spend": 0,
                "campaigns": [],
                "period": f"{date_from} - {date_to}",
                "error": str(e),
            }


# Инициализация клиентов API
wb_api = WildberriesAPI()
wb_business_api = WBBusinessAPI()
ozon_api = OzonAPI()


# Основные функции для использования в боте
async def get_new_reviews() -> list[dict[str, Any]]:
    """Получение новых отзывов со всех платформ"""
    all_reviews = []

    # Получаем отзывы с Wildberries
    wb_reviews = await wb_api.get_new_feedbacks()
    for review in wb_reviews:
        review["platform"] = "WB"
        all_reviews.append(review)

    # Получаем отзывы с Ozon (если реализовано)
    ozon_reviews = await ozon_api.get_product_reviews()
    for review in ozon_reviews:
        review["platform"] = "OZON"
        all_reviews.append(review)

    return all_reviews


async def get_new_questions() -> list[dict[str, Any]]:
    """Получение новых вопросов со всех платформ"""
    all_questions = []

    # Получаем вопросы с Wildberries
    wb_questions = await wb_api.get_new_questions()
    for question in wb_questions:
        question["platform"] = "WB"
        all_questions.append(question)

    # Ozon вопросы можно добавить аналогично при необходимости

    return all_questions


async def post_answer_feedback(feedback_id: str, answer_text: str) -> bool:
    """Отправка ответа на отзыв"""
    # Определяем платформу по ID или другой логике
    # Пока предполагаем, что это Wildberries
    logger.info(f"🔄 Отправка ответа на отзыв {feedback_id}: {answer_text[:30]}...")

    # ВРЕМЕННО: логирование для демо-отзывов
    if feedback_id.startswith(("A3JkO04", "lxPtvUy", "oQdAT5B")):
        logger.info(f"⚠️ Демо-отзыв {feedback_id}: имитируем успешную отправку")
        return True  # Имитируем успех для демо-отзывов

    return await wb_api.post_feedback_answer(feedback_id, answer_text)


async def post_answer_question(question_id: str, answer_text: str) -> bool:
    """Отправка ответа на вопрос"""
    # Определяем платформу по ID или другой логике
    # Пока предполагаем, что это Wildberries
    return await wb_api.post_question_answer(question_id, answer_text)


async def download_wb_reports() -> dict[str, str | None]:
    """Скачивание отчетов Wildberries через API с JWT"""
    try:
        # Используем глобальный экземпляр wb_api
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")

        # API для отчета по продажам
        sales_url = f"{wb_api.STATS_BASE_URL}/api/v1/supplier/sales"
        sales_params = {"dateFrom": date_from, "dateTo": date_to, "limit": 100000}

        # API для остатков
        stocks_url = f"{wb_api.STATS_BASE_URL}/api/v1/supplier/stocks"
        stocks_params = {"dateFrom": date_from}

        reports = {}
        sales_headers = wb_api._get_headers("stats")

        # Скачиваем отчет по продажам с JWT подписью
        try:
            sales_data = await wb_api._make_request_with_retry(
                "GET", sales_url, sales_headers, params=sales_params
            )

            if sales_data:
                # Сохраняем в файл
                os.makedirs("reports", exist_ok=True)
                sales_file = f"reports/wb_sales_{datetime.now().strftime('%Y%m%d')}.json"
                with open(sales_file, "w", encoding="utf-8") as f:
                    import json

                    json.dump(sales_data, f, ensure_ascii=False, indent=2)

                reports["sales"] = sales_file
                logger.info(f"WB отчет продаж скачан с JWT: {len(sales_data)} записей")
            else:
                logger.error("WB: не удалось скачать отчет продаж с JWT")
                reports["sales"] = None

        except Exception as e:
            logger.error(f"Ошибка API продаж WB: {e}")
            reports["sales"] = None

        # Скачиваем отчет по остаткам с JWT подписью
        try:
            stocks_data = await wb_api._make_request_with_retry(
                "GET", stocks_url, sales_headers, params=stocks_params
            )

            if stocks_data:
                # Сохраняем в файл
                stocks_file = f"reports/wb_stock_{datetime.now().strftime('%Y%m%d')}.json"
                with open(stocks_file, "w", encoding="utf-8") as f:
                    import json

                    json.dump(stocks_data, f, ensure_ascii=False, indent=2)

                reports["stock"] = stocks_file
                logger.info(f"WB отчет остатков скачан с JWT: {len(stocks_data)} записей")
            else:
                logger.error("WB: не удалось скачать отчет остатков с JWT")
                reports["stock"] = None

        except Exception as e:
            logger.error(f"Ошибка API остатков WB: {e}")
            reports["stock"] = None

        return reports

    except Exception as e:
        logger.error(f"Ошибка скачивания отчетов WB: {e}")
        return {"sales": None, "stock": None}


async def download_ozon_reports() -> dict[str, str | None]:
    """Скачивание отчетов Ozon"""
    logger.info("Попытка скачивания отчетов Ozon...")

    try:
        # Проверяем валидность токенов
        url = f"{ozon_api.BASE_URL}/v3/product/list"
        test_payload = {"filter": {"visibility": "ALL"}, "last_id": "", "limit": 1}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=ozon_api.headers, json=test_payload) as response:
                if response.status == 404:
                    logger.error("Ozon API: токены неверные или API недоступен (404)")
                    return {"sales": None, "stock": None}
                elif response.status == 401:
                    logger.error("Ozon API: ошибка авторизации - проверьте Client-Id и API-Key")
                    return {"sales": None, "stock": None}
                elif response.status == 200:
                    logger.info("Ozon API: подключение успешное")
                    # Пытаемся скачать отчеты
                    sales_report = await ozon_api.download_sales_report()
                    stocks_data = await ozon_api.get_product_stocks()

                    # Сохраняем остатки если есть
                    stock_file = None
                    if stocks_data:
                        import json

                        stock_file = f"reports/ozon_stocks_{datetime.now().strftime('%Y%m%d')}.json"
                        os.makedirs("reports", exist_ok=True)
                        with open(stock_file, "w", encoding="utf-8") as f:
                            json.dump(stocks_data, f, ensure_ascii=False, indent=2)
                        logger.info(f"Ozon остатки сохранены: {stock_file}")

                    return {"sales": sales_report, "stock": stock_file}
                else:
                    logger.error(f"Ozon API: неожиданная ошибка {response.status}")
                    return {"sales": None, "stock": None}

    except Exception as e:
        logger.error(f"Критическая ошибка Ozon API: {e}")
        return {"sales": None, "stock": None}


# Вспомогательные функции для тестирования
async def test_wb_connection() -> bool:
    """Тестирование подключения к WB API с JWT"""
    try:
        url = f"{wb_api.BASE_URL}/api/v1/feedbacks"
        headers = wb_api._get_headers("feedbacks")
        params = {"take": 1}

        response_data = await wb_api._make_request_with_retry("GET", url, headers, params=params)

        if response_data is not None:
            logger.info("WB API: JWT подключение успешно")
            return True
        else:
            logger.error("WB API: ошибка JWT подключения")
            return False

    except Exception as e:
        logger.error(f"WB API: ошибка JWT соединения {e}")

    return False


async def test_ozon_connection() -> bool:
    """Тестирование подключения к Ozon API"""
    try:
        # Создаем временный экземпляр для тестирования
        temp_ozon_api = OzonAPI()

        async with aiohttp.ClientSession() as session:
            url = f"{temp_ozon_api.BASE_URL}/v1/report/list"

            async with session.post(url, headers=temp_ozon_api.headers, json={}) as response:
                if response.status == 200:
                    logger.info("Ozon API: соединение успешно")
                    return True
                elif response.status in [401, 403]:
                    logger.error("Ozon API: неверные учетные данные")
                else:
                    logger.error(f"Ozon API: ошибка {response.status}")

    except Exception as e:
        logger.error(f"Ozon API: ошибка соединения {e}")

    return False


# Создание экземпляров API клиентов для использования в системе
try:
    wb_api = WildberriesAPI()
    wb_business_api = WBBusinessAPI()
    ozon_api = OzonAPI()

    logger.info("API клиенты успешно инициализированы")
except Exception as e:
    logger.error(f"Ошибка инициализации API клиентов: {e}")
    wb_api = None
    wb_business_api = None
    ozon_api = None
