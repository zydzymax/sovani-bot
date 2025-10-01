"""Система разбивки больших периодов дат на меньшие для API запросов"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class APIChunker:
    """Класс для разбивки больших периодов дат на меньшие чанки для API запросов"""

    # КРИТИЧНО ОПТИМИЗИРОВАННЫЕ периоды для МАКСИМАЛЬНОЙ ПРОИЗВОДИТЕЛЬНОСТИ
    MAX_PERIODS = {
        "wb_sales": 45,  # КРИТИЧНО: Увеличено для меньшего количества чанков
        "wb_orders": 45,  # КРИТИЧНО: Увеличено для меньшего количества чанков
        "wb_advertising": 21,  # КРИТИЧНО: Увеличено с 14 до 21 дня (но все еще осторожно)
        "ozon_fbo": 60,  # КРИТИЧНО: Увеличено до 60 дней (Ozon выдерживает больше)
        "ozon_fbs": 60,  # КРИТИЧНО: Увеличено до 60 дней (Ozon выдерживает больше)
        "ozon_advertising": 60,  # КРИТИЧНО: Увеличено до 60 дней (Ozon выдерживает больше)
    }

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Парсинг строки даты в объект datetime"""
        return datetime.strptime(date_str, "%Y-%m-%d")

    @staticmethod
    def format_date(date_obj: datetime) -> str:
        """Форматирование datetime в строку"""
        return date_obj.strftime("%Y-%m-%d")

    @classmethod
    def chunk_date_range(cls, date_from: str, date_to: str, api_type: str) -> list[tuple[str, str]]:
        """Разбивает период дат на чанки согласно ограничениям API

        Args:
            date_from: Начальная дата в формате YYYY-MM-DD
            date_to: Конечная дата в формате YYYY-MM-DD
            api_type: Тип API для определения максимального периода

        Returns:
            Список кортежей (date_from, date_to) для каждого чанка

        """
        start_date = cls.parse_date(date_from)
        end_date = cls.parse_date(date_to)

        max_days = cls.MAX_PERIODS.get(api_type, 30)
        chunks = []

        current_start = start_date

        while current_start <= end_date:
            # Вычисляем конечную дату для текущего чанка
            current_end = min(current_start + timedelta(days=max_days - 1), end_date)

            chunks.append((cls.format_date(current_start), cls.format_date(current_end)))

            # Переходим к следующему чанку
            current_start = current_end + timedelta(days=1)

        logger.info(
            f"Разбили период {date_from} - {date_to} на {len(chunks)} чанков для API {api_type}"
        )
        return chunks

    @staticmethod
    async def process_chunked_request(
        api_func,
        date_from: str,
        date_to: str,
        api_type: str,
        delay_between_requests: float = 0.5,
        **kwargs,
    ) -> list[Any]:
        """Выполняет API запросы по чанкам и собирает результаты

        Args:
            api_func: Функция API для вызова
            date_from: Начальная дата
            date_to: Конечная дата
            api_type: Тип API для определения размера чанков
            delay_between_requests: Задержка между запросами (сек)
            **kwargs: Дополнительные параметры для API функции

        Returns:
            Список результатов всех чанков

        """
        chunks = APIChunker.chunk_date_range(date_from, date_to, api_type)
        results = []

        logger.info(f"Начинаем обработку {len(chunks)} чанков для {api_type}")

        for i, (chunk_from, chunk_to) in enumerate(chunks, 1):
            try:
                logger.info(f"Обрабатываем чанк {i}/{len(chunks)}: {chunk_from} - {chunk_to}")

                # Выполняем запрос для текущего чанка
                result = await api_func(chunk_from, chunk_to, **kwargs)
                results.append(result)

                # Задержка между запросами для избежания rate limiting
                if i < len(chunks):
                    await asyncio.sleep(delay_between_requests)

            except Exception as e:
                logger.error(f"Ошибка при обработке чанка {chunk_from} - {chunk_to}: {e}")
                # Продолжаем обработку остальных чанков
                results.append(None)

        logger.info(f"Завершена обработка всех чанков для {api_type}")
        return results

    @staticmethod
    def aggregate_wb_sales_data(chunked_results: list[Any]) -> list[dict]:
        """Агрегация результатов WB Sales API с дедупликацией

        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ (30.09.2025):
        Добавлена дедупликация по saleID для устранения многократного учета
        одних и тех же продаж при агрегации чанков.

        ПРОБЛЕМА: API может возвращать одну продажу в нескольких чанках,
        что приводило к завышению данных в 5-10 раз.
        """
        seen_sale_ids = set()
        unique_sales = []
        total_records = 0
        duplicates_removed = 0

        for result in chunked_results:
            if result and isinstance(result, list):
                total_records += len(result)
                for sale in result:
                    sale_id = sale.get("saleID")

                    if sale_id:
                        # Проверяем, видели ли мы эту продажу раньше
                        if sale_id not in seen_sale_ids:
                            seen_sale_ids.add(sale_id)
                            unique_sales.append(sale)
                        else:
                            duplicates_removed += 1
                    else:
                        # Если нет saleID, добавляем запись (но это подозрительно)
                        unique_sales.append(sale)
                        logger.warning(f"⚠️ WB Sale без saleID: {sale}")

        if duplicates_removed > 0:
            logger.warning(
                f"🔍 Дедупликация WB Sales: {total_records} записей → "
                f"{len(unique_sales)} уникальных (удалено {duplicates_removed} дубликатов, "
                f"{duplicates_removed/total_records*100:.1f}%)"
            )
        else:
            logger.info(
                f"✅ WB Sales: {len(unique_sales)} уникальных записей, дубликатов не найдено"
            )

        return unique_sales

    @staticmethod
    def aggregate_wb_orders_data(chunked_results: list[Any]) -> list[dict]:
        """Агрегация результатов WB Orders API с дедупликацией

        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ (30.09.2025):
        Добавлена дедупликация по составному ключу для устранения
        многократного учета одних и тех же заказов.

        ПРОБЛЕМА: Orders API может возвращать один заказ в нескольких чанках.
        У Orders нет уникального ID, поэтому используем составной ключ:
        date + nmId + odid + priceWithDisc
        """
        seen_order_keys = set()
        unique_orders = []
        total_records = 0
        duplicates_removed = 0

        for result in chunked_results:
            if result and isinstance(result, list):
                total_records += len(result)
                for order in result:
                    # Создаем составной ключ для уникальности
                    order_date = order.get("date", "")
                    nm_id = order.get("nmId", "")
                    od_id = order.get("odid", "")
                    price = order.get("priceWithDisc", 0)

                    # Формируем уникальный ключ
                    order_key = f"{order_date}_{nm_id}_{od_id}_{price}"

                    if order_key not in seen_order_keys:
                        seen_order_keys.add(order_key)
                        unique_orders.append(order)
                    else:
                        duplicates_removed += 1

        if duplicates_removed > 0:
            logger.warning(
                f"🔍 Дедупликация WB Orders: {total_records} записей → "
                f"{len(unique_orders)} уникальных (удалено {duplicates_removed} дубликатов, "
                f"{duplicates_removed/total_records*100:.1f}%)"
            )
        else:
            logger.info(
                f"✅ WB Orders: {len(unique_orders)} уникальных записей, дубликатов не найдено"
            )

        return unique_orders

    @staticmethod
    def aggregate_wb_advertising_data(chunked_results: list[Any]) -> dict[str, Any]:
        """Агрегация результатов WB Advertising API"""
        total_spend = 0.0
        total_views = 0
        total_clicks = 0
        campaigns = []

        for result in chunked_results:
            if result and isinstance(result, dict):
                total_spend += result.get("total_spend", 0.0)
                total_views += result.get("total_views", 0)
                total_clicks += result.get("total_clicks", 0)
                if "campaigns" in result:
                    campaigns.extend(result["campaigns"])

        return {
            "total_spend": total_spend,
            "total_views": total_views,
            "total_clicks": total_clicks,
            "campaigns": campaigns,
        }

    @staticmethod
    def aggregate_ozon_data(chunked_results: list[Any]) -> list[dict]:
        """Агрегация результатов Ozon API с дедупликацией

        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ (30.09.2025):
        Добавлена дедупликация по posting_number (номер отправления) или
        составному ключу для FBO/FBS схем.
        """
        seen_posting_numbers = set()
        unique_data = []
        total_records = 0
        duplicates_removed = 0

        for result in chunked_results:
            records = []

            if result and isinstance(result, list):
                records = result
            elif result and isinstance(result, dict) and "result" in result:
                # Некоторые Ozon API возвращают данные в поле "result"
                if isinstance(result["result"], list):
                    records = result["result"]

            total_records += len(records)

            for record in records:
                # Пробуем использовать posting_number как уникальный ID
                posting_number = record.get("posting_number") or record.get("postingNumber")

                if posting_number:
                    if posting_number not in seen_posting_numbers:
                        seen_posting_numbers.add(posting_number)
                        unique_data.append(record)
                    else:
                        duplicates_removed += 1
                else:
                    # Если нет posting_number, создаем составной ключ
                    order_id = record.get("order_id", "")
                    order_number = record.get("order_number", "")
                    created_at = record.get("created_at", "")

                    composite_key = f"{order_id}_{order_number}_{created_at}"

                    if composite_key not in seen_posting_numbers:
                        seen_posting_numbers.add(composite_key)
                        unique_data.append(record)
                    else:
                        duplicates_removed += 1

        if duplicates_removed > 0:
            logger.warning(
                f"🔍 Дедупликация Ozon: {total_records} записей → "
                f"{len(unique_data)} уникальных (удалено {duplicates_removed} дубликатов, "
                f"{duplicates_removed/total_records*100:.1f}%)"
            )
        else:
            logger.info(f"✅ Ozon: {len(unique_data)} уникальных записей, дубликатов не найдено")

        return unique_data


class ChunkedAPIManager:
    """Менеджер для управления chunked API запросами"""

    def __init__(self, api_clients):
        self.api_clients = api_clients
        self.chunker = APIChunker()

    async def get_wb_sales_chunked(self, date_from: str, date_to: str) -> list[dict]:
        """Получение WB Sales данных с разбивкой по чанкам"""

        async def get_wb_sales_for_period(chunk_from: str, chunk_to: str) -> list[dict]:
            """Получение WB продаж за конкретный период"""
            sales_url = f"{self.api_clients.wb_api.STATS_BASE_URL}/api/v1/supplier/sales"
            sales_params = {"dateFrom": chunk_from, "dateTo": chunk_to, "limit": 100000}
            sales_headers = self.api_clients.wb_api._get_headers("stats")

            return (
                await self.api_clients.wb_api._make_request_with_retry(
                    "GET", sales_url, sales_headers, params=sales_params
                )
                or []
            )

        # Определяем задержку в зависимости от размера периода
        from datetime import datetime

        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        period_days = (end_date - start_date).days

        if period_days > 300:  # Год и более - максимальная безопасность
            delay = 8.0  # БЕЗОПАСНОСТЬ: Большая задержка для годовых периодов
            logger.info(f"Годовой период ({period_days} дней) - задержка {delay}s между запросами")
        elif period_days > 180:  # Более полугода
            delay = 5.0  # БЕЗОПАСНОСТЬ: Увеличиваем для надежности
            logger.info(
                f"Очень большой период ({period_days} дней) - задержка {delay}s между запросами"
            )
        elif period_days > 90:  # Более 3 месяцев
            delay = 3.5  # БЕЗОПАСНОСТЬ: Увеличиваем для стабильности
            logger.info(f"Большой период ({period_days} дней) - задержка {delay}s между запросами")
        elif period_days > 30:  # Более месяца
            delay = 2.5  # БЕЗОПАСНОСТЬ: Умеренное увеличение
            logger.info(f"Средний период ({period_days} дней) - задержка {delay}s между запросами")
        else:
            delay = 2.0  # БЕЗОПАСНОСТЬ: Минимальная безопасная задержка
            logger.info(f"Короткий период ({period_days} дней) - задержка {delay}s между запросами")

        results = await self.chunker.process_chunked_request(
            get_wb_sales_for_period, date_from, date_to, "wb_sales", delay_between_requests=delay
        )
        return self.chunker.aggregate_wb_sales_data(results)

    async def get_wb_orders_chunked(self, date_from: str, date_to: str) -> list[dict]:
        """Получение WB Orders данных с разбивкой по чанкам"""

        async def get_wb_orders_for_period(chunk_from: str, chunk_to: str) -> list[dict]:
            """Получение WB заказов за конкретный период"""
            orders_url = f"{self.api_clients.wb_api.STATS_BASE_URL}/api/v1/supplier/orders"
            orders_params = {"dateFrom": chunk_from, "dateTo": chunk_to, "limit": 100000}
            orders_headers = self.api_clients.wb_api._get_headers("stats")

            return (
                await self.api_clients.wb_api._make_request_with_retry(
                    "GET", orders_url, orders_headers, params=orders_params
                )
                or []
            )

        # Используем такую же адаптивную задержку как для Sales
        from datetime import datetime

        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        period_days = (end_date - start_date).days

        if period_days > 300:
            delay = 8.0
        elif period_days > 180:
            delay = 5.0
        elif period_days > 90:
            delay = 3.5
        elif period_days > 30:
            delay = 2.5
        else:
            delay = 2.0

        results = await self.chunker.process_chunked_request(
            get_wb_orders_for_period,
            date_from,
            date_to,
            "wb_orders",
            delay_between_requests=delay,  # БЕЗОПАСНОСТЬ: Адаптивная задержка
        )
        return self.chunker.aggregate_wb_orders_data(results)

    async def get_wb_advertising_chunked(self, date_from: str, date_to: str) -> dict[str, Any]:
        """Получение WB Advertising данных с разбивкой по чанкам"""
        results = await self.chunker.process_chunked_request(
            self.api_clients.wb_business_api.get_advertising_statistics,
            date_from,
            date_to,
            "wb_advertising",
            delay_between_requests=3.0,  # Большая задержка для Adv API
        )
        return self.chunker.aggregate_wb_advertising_data(results)

    async def get_ozon_fbo_chunked(self, date_from: str, date_to: str) -> list[dict]:
        """Получение Ozon FBO данных с разбивкой по чанкам"""
        from datetime import datetime

        from api_clients.ozon.sales_client import OzonSalesClient

        async def get_ozon_fbo_for_period(chunk_from: str, chunk_to: str) -> list[dict]:
            """Получение Ozon FBO заказов за конкретный период"""
            logger.info(f"Получаем Ozon FBO данные за период {chunk_from} - {chunk_to}")
            sales_client = OzonSalesClient()
            date_from_obj = datetime.strptime(chunk_from, "%Y-%m-%d").date()
            date_to_obj = datetime.strptime(chunk_to, "%Y-%m-%d").date()

            try:
                fbo_data = await sales_client.get_fbo_orders(date_from_obj, date_to_obj)
                logger.info(
                    f"Ozon FBO: получено {len(fbo_data) if fbo_data else 0} записей за {chunk_from} - {chunk_to}"
                )

                # Обрабатываем разные форматы ответа
                if isinstance(fbo_data, dict):
                    result = fbo_data.get("result", {})
                    if isinstance(result, dict):
                        return result.get("postings", [])
                    elif isinstance(result, list):
                        return result
                    else:
                        return []
                elif isinstance(fbo_data, list):
                    return fbo_data
                else:
                    return []

            except Exception as e:
                logger.error(f"Ошибка получения Ozon FBO для {chunk_from}-{chunk_to}: {e}")
                return []

        # Адаптивная задержка для Ozon FBO
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        period_days = (end_date - start_date).days

        if period_days > 300:
            delay = 4.0  # Год
        elif period_days > 180:
            delay = 3.0  # Полугодие
        elif period_days > 90:
            delay = 2.5  # Квартал
        else:
            delay = 2.0  # Короткие периоды

        results = await self.chunker.process_chunked_request(
            get_ozon_fbo_for_period, date_from, date_to, "ozon_fbo", delay_between_requests=delay
        )
        return self.chunker.aggregate_ozon_data(results)

    async def get_ozon_fbs_chunked(self, date_from: str, date_to: str) -> list[dict]:
        """Получение Ozon FBS данных с разбивкой по чанкам"""
        from datetime import datetime

        from api_clients.ozon.sales_client import OzonSalesClient

        async def get_ozon_transactions_for_period(chunk_from: str, chunk_to: str) -> list[dict]:
            """Получение Ozon транзакций за конкретный период"""
            logger.info(f"Получаем Ozon FBS транзакции за период {chunk_from} - {chunk_to}")
            sales_client = OzonSalesClient()
            date_from_obj = datetime.strptime(chunk_from, "%Y-%m-%d").date()
            date_to_obj = datetime.strptime(chunk_to, "%Y-%m-%d").date()

            transactions = await sales_client.get_transactions(date_from_obj, date_to_obj)
            logger.info(
                f"Ozon FBS: получено {len(transactions) if transactions else 0} транзакций за {chunk_from} - {chunk_to}"
            )
            return transactions if transactions else []

        # Адаптивная задержка для Ozon FBS
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        period_days = (end_date - start_date).days

        if period_days > 300:
            delay = 4.0  # Год
        elif period_days > 180:
            delay = 3.0  # Полугодие
        elif period_days > 90:
            delay = 2.5  # Квартал
        else:
            delay = 2.0  # Короткие периоды

        results = await self.chunker.process_chunked_request(
            get_ozon_transactions_for_period,
            date_from,
            date_to,
            "ozon_fbs",
            delay_between_requests=delay,
        )
        return self.chunker.aggregate_ozon_data(results)
