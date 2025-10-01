"""⚡ МОДУЛЬ ОПТИМИЗАЦИИ ПРОИЗВОДИТЕЛЬНОСТИ

Включает кэширование, пулинг соединений и оптимизацию алгоритмов
для максимальной производительности системы аналитики.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Запись в кэше с временем истечения"""

    data: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_access: datetime | None = None


class PerformanceOptimizer:
    """Оптимизатор производительности системы"""

    def __init__(self, default_ttl_minutes: int = 30):
        self.cache: dict[str, CacheEntry] = {}
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self.cache_stats = {"hits": 0, "misses": 0, "evictions": 0}
        # Максимальный размер кэша для предотвращения утечки памяти
        self.max_cache_size = 1000

    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Генерация ключа кэша на основе параметров"""
        # Сортируем kwargs для консистентности ключей
        sorted_kwargs = sorted(kwargs.items())
        content = f"{prefix}:{json.dumps(sorted_kwargs, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()

    def _cleanup_expired(self) -> None:
        """Очистка истёкших записей кэша"""
        now = datetime.now()
        expired_keys = [key for key, entry in self.cache.items() if entry.expires_at < now]

        for key in expired_keys:
            del self.cache[key]
            self.cache_stats["evictions"] += 1

        # Если кэш слишком большой, удаляем самые старые записи
        if len(self.cache) > self.max_cache_size:
            # Сортируем по времени последнего доступа
            sorted_entries = sorted(
                self.cache.items(), key=lambda x: x[1].last_access or x[1].created_at
            )

            # Удаляем 20% старых записей
            to_remove = len(self.cache) // 5
            for key, _ in sorted_entries[:to_remove]:
                del self.cache[key]
                self.cache_stats["evictions"] += 1

    def get_cached(self, cache_key: str) -> Any | None:
        """Получение данных из кэша"""
        self._cleanup_expired()

        if cache_key in self.cache:
            entry = self.cache[cache_key]
            entry.access_count += 1
            entry.last_access = datetime.now()
            self.cache_stats["hits"] += 1
            logger.debug(f"📋 Cache HIT: {cache_key[:8]}...")
            return entry.data

        self.cache_stats["misses"] += 1
        logger.debug(f"💔 Cache MISS: {cache_key[:8]}...")
        return None

    def set_cached(self, cache_key: str, data: Any, ttl_minutes: int | None = None) -> None:
        """Сохранение данных в кэш"""
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self.default_ttl
        now = datetime.now()

        entry = CacheEntry(
            data=data, created_at=now, expires_at=now + ttl, access_count=1, last_access=now
        )

        self.cache[cache_key] = entry
        logger.debug(f"💾 Cache SET: {cache_key[:8]}... (TTL: {ttl_minutes or 30}m)")

    def cache_api_response(self, api_name: str, method: str, **params):
        """Декоратор для кэширования ответов API"""

        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Генерируем ключ кэша
                cache_key = self._generate_cache_key(f"{api_name}:{method}", **params, **kwargs)

                # Проверяем кэш
                cached_result = self.get_cached(cache_key)
                if cached_result is not None:
                    return cached_result

                # Выполняем запрос
                result = await func(*args, **kwargs)

                # Кэшируем результат (API данные кэшируем на 15 минут)
                self.set_cached(cache_key, result, ttl_minutes=15)

                return result

            return wrapper

        return decorator

    def get_cache_stats(self) -> dict[str, Any]:
        """Получение статистики кэша"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_size": len(self.cache),
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "hits": self.cache_stats["hits"],
            "misses": self.cache_stats["misses"],
            "evictions": self.cache_stats["evictions"],
        }

    def clear_cache(self, pattern: str | None = None) -> int:
        """Очистка кэша (полная или по паттерну)"""
        if pattern is None:
            cleared = len(self.cache)
            self.cache.clear()
            logger.info(f"🧹 Очищен весь кэш: {cleared} записей")
            return cleared

        # Очистка по паттерну (простая фильтрация по вхождению подстроки)
        keys_to_remove = [key for key in self.cache.keys() if pattern in key]
        for key in keys_to_remove:
            del self.cache[key]

        logger.info(f"🧹 Очищен кэш по паттерну '{pattern}': {len(keys_to_remove)} записей")
        return len(keys_to_remove)


class DataProcessor:
    """Оптимизированный процессор данных"""

    @staticmethod
    def batch_process_sales(
        sales_data: list[dict[str, Any]], batch_size: int = 1000
    ) -> dict[str, Any]:
        """Пакетная обработка данных продаж для улучшения производительности"""
        if not sales_data:
            return {"total_revenue": 0, "total_items": 0, "processed_batches": 0}

        total_revenue = 0
        total_items = 0
        processed_batches = 0

        # Обрабатываем данные батчами для экономии памяти
        for i in range(0, len(sales_data), batch_size):
            batch = sales_data[i : i + batch_size]

            # Векторизованная обработка батча
            batch_revenue = sum(
                sale.get("forPay", 0)
                for sale in batch
                if isinstance(sale.get("forPay"), (int, float))
            )

            total_revenue += batch_revenue
            total_items += len(batch)
            processed_batches += 1

        logger.debug(f"⚡ Обработано {total_items} продаж за {processed_batches} батчей")

        return {
            "total_revenue": total_revenue,
            "total_items": total_items,
            "processed_batches": processed_batches,
        }

    @staticmethod
    def optimize_date_filtering(
        data: list[dict[str, Any]], date_field: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        """Оптимизированная фильтрация по датам"""
        if not data:
            return []

        # Предварительная проверка формата дат в первых записях
        sample_size = min(10, len(data))
        date_formats = set()

        for item in data[:sample_size]:
            if item.get(date_field):
                date_str = item[date_field]
                if "T" in date_str:
                    date_formats.add("iso_with_time")
                elif "." in date_str:
                    date_formats.add("dot_format")
                else:
                    date_formats.add("iso_date")

        # Выбираем наиболее подходящую стратегию фильтрации
        if "iso_with_time" in date_formats:
            return [
                item
                for item in data
                if date_field in item
                and item[date_field]
                and date_from <= item[date_field].split("T")[0] <= date_to
            ]
        else:
            return [
                item
                for item in data
                if date_field in item
                and item[date_field]
                and date_from <= item[date_field][:10] <= date_to
            ]


# Глобальный экземпляр оптимизатора
performance_optimizer = PerformanceOptimizer()


def get_performance_stats() -> dict[str, Any]:
    """Получение общей статистики производительности"""
    cache_stats = performance_optimizer.get_cache_stats()

    return {
        "cache_stats": cache_stats,
        "optimizer_status": "active",
        "recommendations": _generate_performance_recommendations(cache_stats),
    }


def _generate_performance_recommendations(cache_stats: dict[str, Any]) -> list[str]:
    """Генерация рекомендаций по производительности"""
    recommendations = []

    hit_rate = cache_stats.get("hit_rate_percent", 0)

    if hit_rate < 30:
        recommendations.append("📈 Низкий уровень попаданий в кэш. Рассмотрите увеличение TTL")
    elif hit_rate > 80:
        recommendations.append("🎯 Отличный уровень кэширования!")

    cache_size = cache_stats.get("cache_size", 0)
    if cache_size > 800:
        recommendations.append("🧹 Большой размер кэша. Рекомендуется очистка")

    evictions = cache_stats.get("evictions", 0)
    if evictions > 100:
        recommendations.append("♻️ Много вытеснений из кэша. Рассмотрите увеличение размера кэша")

    return recommendations or ["✅ Производительность в норме"]


def optimize_chunking_strategy(
    total_days: int, api_type: str, target_chunks: int = 10
) -> tuple[int, int]:
    """Оптимизация стратегии разбивки на чанки

    Args:
        total_days: Общее количество дней для обработки
        api_type: Тип API (wb_sales, ozon_fbo и т.д.)
        target_chunks: Желаемое количество чанков

    Returns:
        Tuple[int, int]: (оптимальный_размер_чанка, количество_чанков)

    """
    # Максимальные размеры чанков для разных API
    max_chunk_sizes = {
        "wb_sales": 28,
        "wb_orders": 28,
        "wb_advertising": 14,
        "ozon_fbo": 30,
        "ozon_fbs": 30,
    }

    max_chunk = max_chunk_sizes.get(api_type, 30)

    # Если общий период меньше максимального чанка, используем один чанк
    if total_days <= max_chunk:
        return total_days, 1

    # Рассчитываем оптимальный размер чанка
    optimal_chunk_size = min(max_chunk, max(1, total_days // target_chunks))
    actual_chunks = (total_days + optimal_chunk_size - 1) // optimal_chunk_size

    logger.debug(
        f"⚡ Оптимизация чанкинга {api_type}: {total_days} дней → {actual_chunks} чанков по {optimal_chunk_size} дней"
    )

    return optimal_chunk_size, actual_chunks
