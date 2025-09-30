"""
Оптимизированный API клиент с объединением запросов и умными задержками
"""
import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import json
from dataclasses import dataclass
from api_clients_main import WildberriesAPI, OzonAPI, WBBusinessAPI

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """Пакетный запрос для оптимизации"""
    api_type: str
    endpoint: str
    params: Dict[str, Any]
    headers: Dict[str, str]
    priority: int = 1  # 1 - высокий, 2 - обычный, 3 - низкий


class OptimizedAPIClient:
    """Оптимизированный API клиент с пакетными запросами"""

    def __init__(self):
        self.wb_api = WildberriesAPI()
        self.ozon_api = OzonAPI()
        self.wb_business_api = WBBusinessAPI()
        self._session_pool = {}
        self._rate_limits = {
            'wb_orders': {'requests': 0, 'window_start': datetime.now(), 'max_per_minute': 25},
            'wb_sales': {'requests': 0, 'window_start': datetime.now(), 'max_per_minute': 25},
            'wb_advertising': {'requests': 0, 'window_start': datetime.now(), 'max_per_minute': 15},
            'ozon_api': {'requests': 0, 'window_start': datetime.now(), 'max_per_minute': 30},
        }

    @asynccontextmanager
    async def get_session(self, api_type: str):
        """Получение сессии для конкретного API"""
        if api_type not in self._session_pool:
            timeout = aiohttp.ClientTimeout(total=300, connect=30)
            connector = aiohttp.TCPConnector(
                limit=10,  # Общий лимит соединений
                limit_per_host=5,  # Лимит на хост
                ttl_dns_cache=300,  # TTL DNS кеша
                use_dns_cache=True,
            )
            self._session_pool[api_type] = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )

        try:
            yield self._session_pool[api_type]
        finally:
            pass  # Сессия остается открытой для переиспользования

    async def close_all_sessions(self):
        """Закрытие всех сессий"""
        for session in self._session_pool.values():
            await session.close()
        self._session_pool.clear()

    async def _check_rate_limit(self, api_type: str) -> float:
        """Проверка rate limit и возврат необходимой задержки"""
        now = datetime.now()
        rate_info = self._rate_limits[api_type]

        # Сброс счетчика если прошла минута
        if (now - rate_info['window_start']).total_seconds() >= 60:
            rate_info['requests'] = 0
            rate_info['window_start'] = now

        # Проверяем превышение лимита
        if rate_info['requests'] >= rate_info['max_per_minute']:
            # Нужно ждать до начала новой минуты
            seconds_to_wait = 60 - (now - rate_info['window_start']).total_seconds()
            logger.info(f"Rate limit для {api_type}: ждем {seconds_to_wait:.1f}с")
            return max(seconds_to_wait, 0)

        return 0

    async def _execute_request_with_rate_limit(self, api_type: str, request_func) -> Any:
        """Выполнение запроса с соблюдением rate limit"""
        # Проверяем rate limit
        delay = await self._check_rate_limit(api_type)
        if delay > 0:
            await asyncio.sleep(delay)

        # Увеличиваем счетчик запросов
        self._rate_limits[api_type]['requests'] += 1

        # Выполняем запрос
        return await request_func()

    async def batch_wb_data(self, date_chunks: List[Tuple[str, str]]) -> Dict[str, List]:
        """Пакетное получение WB данных (заказы + продажи одновременно)"""
        results = {
            'orders': [],
            'sales': []
        }

        # Группируем запросы по приоритету
        high_priority_chunks = date_chunks[:3]  # Первые 3 чанка с высоким приоритетом
        regular_chunks = date_chunks[3:]

        # Обрабатываем высокоприоритетные чанки последовательно
        for chunk_from, chunk_to in high_priority_chunks:
            logger.info(f"Обработка приоритетного WB чанка: {chunk_from} - {chunk_to}")

            # Запускаем заказы и продажи параллельно для одного периода
            orders_task = self._get_wb_orders_optimized(chunk_from, chunk_to)
            sales_task = self._get_wb_sales_optimized(chunk_from, chunk_to)

            orders_data, sales_data = await asyncio.gather(orders_task, sales_task, return_exceptions=True)

            if not isinstance(orders_data, Exception) and orders_data:
                results['orders'].extend(orders_data)

            if not isinstance(sales_data, Exception) and sales_data:
                results['sales'].extend(sales_data)

            # Задержка между приоритетными чанками
            await asyncio.sleep(8.0)

        # Обрабатываем остальные чанки с большими задержками
        for chunk_from, chunk_to in regular_chunks:
            logger.info(f"Обработка обычного WB чанка: {chunk_from} - {chunk_to}")

            try:
                # Для обычных чанков делаем задержку побольше
                await asyncio.sleep(12.0)

                orders_data = await self._get_wb_orders_optimized(chunk_from, chunk_to)
                if orders_data:
                    results['orders'].extend(orders_data)

                await asyncio.sleep(5.0)  # Между заказами и продажами

                sales_data = await self._get_wb_sales_optimized(chunk_from, chunk_to)
                if sales_data:
                    results['sales'].extend(sales_data)

            except Exception as e:
                logger.error(f"Ошибка обработки WB чанка {chunk_from}-{chunk_to}: {e}")
                continue

        return results

    async def _get_wb_orders_optimized(self, date_from: str, date_to: str) -> List[Dict]:
        """Оптимизированное получение WB заказов"""
        async def request_func():
            async with self.get_session('wb_api') as session:
                url = f"{self.wb_api.STATS_BASE_URL}/api/v1/supplier/orders"
                params = {
                    'dateFrom': date_from,
                    'dateTo': date_to,
                    'limit': 100000  # Максимальный лимит за раз
                }
                headers = self.wb_api._get_headers('stats')

                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        logger.warning(f"429 для WB orders {date_from}-{date_to}, повторяем через 60с")
                        await asyncio.sleep(60)
                        return await request_func()  # Рекурсивный повтор
                    else:
                        logger.error(f"WB orders API error {response.status} for {date_from}-{date_to}")
                        return []

        return await self._execute_request_with_rate_limit('wb_orders', request_func)

    async def _get_wb_sales_optimized(self, date_from: str, date_to: str) -> List[Dict]:
        """Оптимизированное получение WB продаж"""
        async def request_func():
            async with self.get_session('wb_api') as session:
                url = f"{self.wb_api.STATS_BASE_URL}/api/v1/supplier/sales"
                params = {
                    'dateFrom': date_from,
                    'dateTo': date_to,
                    'limit': 100000  # Максимальный лимит за раз
                }
                headers = self.wb_api._get_headers('stats')

                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        logger.warning(f"429 для WB sales {date_from}-{date_to}, повторяем через 60с")
                        await asyncio.sleep(60)
                        return await request_func()  # Рекурсивный повтор
                    else:
                        logger.error(f"WB sales API error {response.status} for {date_from}-{date_to}")
                        return []

        return await self._execute_request_with_rate_limit('wb_sales', request_func)

    async def batch_ozon_data(self, date_chunks: List[Tuple[str, str]]) -> Dict[str, List]:
        """Пакетное получение Ozon данных"""
        results = {
            'fbo_orders': [],
            'fbs_transactions': []
        }

        # Обрабатываем чанки последовательно с оптимальными задержками
        for i, (chunk_from, chunk_to) in enumerate(date_chunks):
            logger.info(f"Обработка Ozon чанка {i+1}/{len(date_chunks)}: {chunk_from} - {chunk_to}")

            try:
                # FBO и FBS можно запрашивать параллельно для одного периода
                fbo_task = self._get_ozon_fbo_optimized(chunk_from, chunk_to)
                fbs_task = self._get_ozon_fbs_optimized(chunk_from, chunk_to)

                fbo_data, fbs_data = await asyncio.gather(fbo_task, fbs_task, return_exceptions=True)

                if not isinstance(fbo_data, Exception) and fbo_data:
                    results['fbo_orders'].extend(fbo_data)

                if not isinstance(fbs_data, Exception) and fbs_data:
                    results['fbs_transactions'].extend(fbs_data)

                # Задержка между чанками Ozon
                if i < len(date_chunks) - 1:
                    await asyncio.sleep(3.0)

            except Exception as e:
                logger.error(f"Ошибка обработки Ozon чанка {chunk_from}-{chunk_to}: {e}")
                continue

        return results

    async def _get_ozon_fbo_optimized(self, date_from: str, date_to: str) -> List[Dict]:
        """Оптимизированное получение Ozon FBO"""
        try:
            from api_clients.ozon.sales_client import OzonSalesClient
            sales_client = OzonSalesClient()

            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()

            async def request_func():
                return await sales_client.get_fbo_orders(date_from_obj, date_to_obj)

            fbo_data = await self._execute_request_with_rate_limit('ozon_api', request_func)

            # Обрабатываем ответ
            if isinstance(fbo_data, dict):
                result = fbo_data.get('result', {})
                if isinstance(result, dict):
                    return result.get('postings', [])
                elif isinstance(result, list):
                    return result
            elif isinstance(fbo_data, list):
                return fbo_data

            return []

        except Exception as e:
            logger.error(f"Ошибка получения Ozon FBO для {date_from}-{date_to}: {e}")
            return []

    async def _get_ozon_fbs_optimized(self, date_from: str, date_to: str) -> List[Dict]:
        """Оптимизированное получение Ozon FBS"""
        try:
            from api_clients.ozon.sales_client import OzonSalesClient
            sales_client = OzonSalesClient()

            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()

            async def request_func():
                return await sales_client.get_transactions(date_from_obj, date_to_obj)

            return await self._execute_request_with_rate_limit('ozon_api', request_func)

        except Exception as e:
            logger.error(f"Ошибка получения Ozon FBS для {date_from}-{date_to}: {e}")
            return []

    async def get_wb_advertising_batch(self, date_chunks: List[Tuple[str, str]]) -> Dict[str, Any]:
        """Пакетное получение рекламных данных WB"""
        total_spend = 0.0
        total_views = 0
        total_clicks = 0
        all_campaigns = []

        for chunk_from, chunk_to in date_chunks:
            try:
                logger.info(f"Получение WB рекламы для {chunk_from} - {chunk_to}")

                async def request_func():
                    return await self.wb_business_api.get_fullstats_v3(chunk_from, chunk_to)

                chunk_data = await self._execute_request_with_rate_limit('wb_advertising', request_func)

                if chunk_data:
                    total_spend += chunk_data.get("total_spend", 0.0)
                    total_views += chunk_data.get("total_views", 0)
                    total_clicks += chunk_data.get("total_clicks", 0)
                    if "campaigns" in chunk_data:
                        all_campaigns.extend(chunk_data["campaigns"])

                # Большая задержка для рекламного API
                await asyncio.sleep(5.0)

            except Exception as e:
                logger.error(f"Ошибка получения WB рекламы для {chunk_from}-{chunk_to}: {e}")
                continue

        return {
            "total_spend": total_spend,
            "total_views": total_views,
            "total_clicks": total_clicks,
            "campaigns": all_campaigns
        }

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Статистика оптимизации запросов"""
        return {
            'rate_limits': self._rate_limits,
            'active_sessions': len(self._session_pool),
            'optimization_features': [
                'Пакетные запросы по чанкам',
                'Параллельные запросы внутри чанка',
                'Умные задержки по приоритету',
                'Переиспользование HTTP сессий',
                'Автоматические повторы при 429',
                'Rate limiting по типам API'
            ]
        }