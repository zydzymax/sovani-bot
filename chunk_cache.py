"""
Система кеширования промежуточных результатов чанков в Redis
"""
import json
import logging
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import redis
import aioredis
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ChunkCache:
    """Кеш для промежуточных результатов обработки чанков"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self._async_client = None

    async def get_async_client(self):
        """Получение асинхронного клиента Redis"""
        if self._async_client is None:
            self._async_client = await aioredis.from_url(self.redis_url)
        return self._async_client

    def _generate_cache_key(self, api_type: str, date_from: str, date_to: str, extra_params: str = "") -> str:
        """Генерация уникального ключа кеша"""
        # Создаем хеш из параметров для уникальности
        params_string = f"{api_type}_{date_from}_{date_to}_{extra_params}"
        hash_key = hashlib.md5(params_string.encode()).hexdigest()[:8]
        return f"chunk:{api_type}:{date_from}:{date_to}:{hash_key}"

    def get_chunk_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Получение данных чанка из кеша"""
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                # Проверяем, не истек ли кеш
                if 'cached_at' in data:
                    cached_time = datetime.fromisoformat(data['cached_at'])
                    if datetime.now() - cached_time < timedelta(hours=24):
                        logger.info(f"Найден валидный кеш: {cache_key}")
                        return data
                    else:
                        # Удаляем истекший кеш
                        self.redis_client.delete(cache_key)
                        logger.info(f"Удален истекший кеш: {cache_key}")
        except Exception as e:
            logger.error(f"Ошибка получения кеша {cache_key}: {e}")

        return None

    def save_chunk_data(self, cache_key: str, data: Dict[str, Any], expiry_hours: int = 24):
        """Сохранение данных чанка в кеш"""
        try:
            # Добавляем метаданные
            cache_data = {
                'data': data,
                'cached_at': datetime.now().isoformat(),
                'expiry_hours': expiry_hours
            }

            # Сохраняем с TTL
            ttl_seconds = expiry_hours * 3600
            self.redis_client.setex(cache_key, ttl_seconds, json.dumps(cache_data, default=str))

            logger.info(f"Сохранен кеш: {cache_key}, TTL: {expiry_hours}ч")

        except Exception as e:
            logger.error(f"Ошибка сохранения кеша {cache_key}: {e}")

    async def get_wb_chunk_cached(self, date_from: str, date_to: str) -> Optional[Dict[str, Any]]:
        """Получение WB данных из кеша"""
        cache_key = self._generate_cache_key('wb', date_from, date_to)
        cached = self.get_chunk_data(cache_key)
        if cached:
            return cached.get('data')
        return None

    async def save_wb_chunk_cached(self, date_from: str, date_to: str, data: Dict[str, Any]):
        """Сохранение WB данных в кеш"""
        cache_key = self._generate_cache_key('wb', date_from, date_to)
        self.save_chunk_data(cache_key, data)

    async def get_ozon_chunk_cached(self, date_from: str, date_to: str) -> Optional[Dict[str, Any]]:
        """Получение Ozon данных из кеша"""
        cache_key = self._generate_cache_key('ozon', date_from, date_to)
        cached = self.get_chunk_data(cache_key)
        if cached:
            return cached.get('data')
        return None

    async def save_ozon_chunk_cached(self, date_from: str, date_to: str, data: Dict[str, Any]):
        """Сохранение Ozon данных в кеш"""
        cache_key = self._generate_cache_key('ozon', date_from, date_to)
        self.save_chunk_data(cache_key, data)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Статистика кеша"""
        try:
            # Получаем все ключи кеша чанков
            chunk_keys = self.redis_client.keys("chunk:*")

            stats = {
                'total_chunks': len(chunk_keys),
                'wb_chunks': len([k for k in chunk_keys if ':wb:' in k]),
                'ozon_chunks': len([k for k in chunk_keys if ':ozon:' in k]),
                'cache_sizes': {},
                'oldest_cache': None,
                'newest_cache': None
            }

            # Анализируем размеры и время создания
            oldest_time = None
            newest_time = None

            for key in chunk_keys[:10]:  # Ограничиваем для производительности
                try:
                    cached_data = self.redis_client.get(key)
                    if cached_data:
                        data = json.loads(cached_data)
                        size_kb = len(cached_data) / 1024
                        stats['cache_sizes'][key] = f"{size_kb:.1f} KB"

                        if 'cached_at' in data:
                            cache_time = datetime.fromisoformat(data['cached_at'])
                            if oldest_time is None or cache_time < oldest_time:
                                oldest_time = cache_time
                                stats['oldest_cache'] = key
                            if newest_time is None or cache_time > newest_time:
                                newest_time = cache_time
                                stats['newest_cache'] = key
                except:
                    continue

            return stats

        except Exception as e:
            logger.error(f"Ошибка получения статистики кеша: {e}")
            return {'error': str(e)}

    def cleanup_expired(self):
        """Очистка истекших записей кеша"""
        try:
            chunk_keys = self.redis_client.keys("chunk:*")
            deleted = 0

            for key in chunk_keys:
                try:
                    ttl = self.redis_client.ttl(key)
                    if ttl == -2:  # Ключ не существует
                        deleted += 1
                    elif ttl == -1:  # Ключ без TTL (не должно быть)
                        # Проверяем время создания
                        cached_data = self.redis_client.get(key)
                        if cached_data:
                            data = json.loads(cached_data)
                            if 'cached_at' in data:
                                cached_time = datetime.fromisoformat(data['cached_at'])
                                if datetime.now() - cached_time > timedelta(hours=48):  # Старше 48 часов
                                    self.redis_client.delete(key)
                                    deleted += 1
                except:
                    continue

            logger.info(f"Очистка кеша завершена: удалено {deleted} записей")
            return deleted

        except Exception as e:
            logger.error(f"Ошибка очистки кеша: {e}")
            return 0

    def invalidate_cache_pattern(self, pattern: str):
        """Инвалидация кеша по шаблону"""
        try:
            keys = self.redis_client.keys(f"chunk:*{pattern}*")
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Инвалидирован кеш по шаблону '{pattern}': {deleted} ключей")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Ошибка инвалидации кеша: {e}")
            return 0

    def get_chunk_status(self, date_from: str, date_to: str) -> Dict[str, str]:
        """Проверка статуса кеша для периода"""
        wb_key = self._generate_cache_key('wb', date_from, date_to)
        ozon_key = self._generate_cache_key('ozon', date_from, date_to)

        status = {
            'wb_cached': 'no',
            'ozon_cached': 'no',
            'wb_key': wb_key,
            'ozon_key': ozon_key
        }

        # Проверяем WB кеш
        if self.get_chunk_data(wb_key):
            status['wb_cached'] = 'yes'

        # Проверяем Ozon кеш
        if self.get_chunk_data(ozon_key):
            status['ozon_cached'] = 'yes'

        return status


class CachedAPIProcessor:
    """Обработчик API с поддержкой кеширования"""

    def __init__(self):
        self.cache = ChunkCache()
        from real_data_reports import RealDataFinancialReports
        self.reports = RealDataFinancialReports()

    async def get_wb_data_cached(self, date_from: str, date_to: str) -> Dict[str, Any]:
        """Получение WB данных с кешированием"""
        # Проверяем кеш
        cached_data = await self.cache.get_wb_chunk_cached(date_from, date_to)
        if cached_data:
            logger.info(f"Использован WB кеш для {date_from}-{date_to}")
            return cached_data

        # Получаем данные из API
        logger.info(f"Получение WB данных из API для {date_from}-{date_to}")
        data = await self.reports.get_real_wb_data(date_from, date_to)

        # Сохраняем в кеш
        await self.cache.save_wb_chunk_cached(date_from, date_to, data)

        return data

    async def get_ozon_data_cached(self, date_from: str, date_to: str) -> Dict[str, Any]:
        """Получение Ozon данных с кешированием"""
        # Проверяем кеш
        cached_data = await self.cache.get_ozon_chunk_cached(date_from, date_to)
        if cached_data:
            logger.info(f"Использован Ozon кеш для {date_from}-{date_to}")
            return cached_data

        # Получаем данные из API
        logger.info(f"Получение Ozon данных из API для {date_from}-{date_to}")
        data = await self.reports.get_real_ozon_sales(date_from, date_to)

        # Сохраняем в кеш
        await self.cache.save_ozon_chunk_cached(date_from, date_to, data)

        return data