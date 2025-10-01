"""Централизованная система управления лимитами API запросов"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Конфигурация лимитов для API"""

    requests_per_minute: int
    min_interval_ms: int  # Минимальный интервал между запросами в миллисекундах
    burst_limit: int  # Количество запросов в "burst" режиме
    retry_delay_base: int = 60  # Базовая задержка при 429 ошибке
    retry_delay_multiplier: int = 30  # Множитель задержки для повторных попыток


class RateLimiter:
    """Централизованный управляющий лимитами API запросов"""

    # КАРДИНАЛЬНО ПЕРЕСМОТРЕННЫЕ ЛИМИТЫ ДЛЯ МАКСИМАЛЬНОЙ БЕЗОПАСНОСТИ
    CONFIGS = {
        "wb_general": RateLimitConfig(
            requests_per_minute=45,  # ОПТИМИЗАЦИЯ: Увеличиваем до 45 для скорости
            min_interval_ms=1500,  # ОПТИМИЗАЦИЯ: 1.5 секунды между запросами
            burst_limit=4,  # ОПТИМИЗАЦИЯ: Увеличиваем burst до 4
            retry_delay_base=120,  # КРИТИЧНО: Увеличена базовая задержка при 429
            retry_delay_multiplier=60,  # КРИТИЧНО: Агрессивная задержка при повторных 429
        ),
        "wb_advertising": RateLimitConfig(
            requests_per_minute=5,  # КРИТИЧНО: ЭКСТРЕМАЛЬНЫЙ лимит (найдено эмпирически)
            min_interval_ms=60000,  # КРИТИЧНО: 60 секунд между запросами!
            burst_limit=1,  # КРИТИЧНО: Только 1 запрос за раз
            retry_delay_base=300,  # КРИТИЧНО: 5 минут базовой задержки при 429
            retry_delay_multiplier=180,  # КРИТИЧНО: 3 минуты за каждую попытку
        ),
        "ozon_general": RateLimitConfig(
            requests_per_minute=120,  # КРИТИЧНО: Снижен с 300 до 120 для надежности
            min_interval_ms=500,  # КРИТИЧНО: 0.5 секунды между запросами для Ozon
            burst_limit=5,  # КРИТИЧНО: Умеренный burst лимит
            retry_delay_base=90,  # Стандартная задержка при 429
            retry_delay_multiplier=30,  # Умеренное увеличение при повторах
        ),
        "ozon_performance": RateLimitConfig(
            requests_per_minute=120,  # КРИТИЧНО: Соответствует ozon_general
            min_interval_ms=500,
            burst_limit=5,
        ),
    }

    def __init__(self):
        self.last_request_times: dict[str, float] = {}
        self.request_counts: dict[str, list] = defaultdict(list)
        self.burst_tokens: dict[str, int] = {}

        # Инициализация burst токенов
        for api_name, config in self.CONFIGS.items():
            self.burst_tokens[api_name] = config.burst_limit

    async def wait_for_rate_limit(self, api_name: str) -> None:
        """Ожидание соблюдения лимитов для указанного API

        Args:
            api_name: Название API ('wb_general', 'wb_advertising', 'ozon_general', etc.)

        """
        if api_name not in self.CONFIGS:
            logger.warning(f"Неизвестный API: {api_name}, используем общие лимиты")
            api_name = "wb_general"

        config = self.CONFIGS[api_name]
        current_time = time.time()

        # Очищаем старые записи (старше 1 минуты)
        minute_ago = current_time - 60
        self.request_counts[api_name] = [t for t in self.request_counts[api_name] if t > minute_ago]

        # Проверяем лимит запросов в минуту
        if len(self.request_counts[api_name]) >= config.requests_per_minute:
            wait_time = 60 - (current_time - self.request_counts[api_name][0])
            if wait_time > 0:
                logger.info(
                    f"{api_name}: Достигнут лимит {config.requests_per_minute} req/min, ждем {wait_time:.1f}с"
                )
                await asyncio.sleep(wait_time)
                current_time = time.time()

        # Проверяем минимальный интервал между запросами
        if api_name in self.last_request_times:
            time_since_last = (current_time - self.last_request_times[api_name]) * 1000
            min_interval = config.min_interval_ms

            if time_since_last < min_interval:
                wait_time = (min_interval - time_since_last) / 1000
                logger.debug(f"{api_name}: Ждем {wait_time:.2f}с (min interval {min_interval}ms)")
                await asyncio.sleep(wait_time)
                current_time = time.time()

        # ИСПРАВЛЕНО: Более эффективное управление burst токенами
        if self.burst_tokens[api_name] <= 0:
            # Восстанавливаем burst токены по времени, а не ожиданием
            time_since_last = current_time - self.last_request_times.get(api_name, 0)

            if time_since_last >= (config.min_interval_ms / 1000):
                # Восстанавливаем токены пропорционально прошедшему времени
                tokens_to_restore = min(
                    config.burst_limit, int(time_since_last / (config.min_interval_ms / 1000))
                )
                self.burst_tokens[api_name] = min(config.burst_limit, tokens_to_restore)
                logger.debug(f"{api_name}: Восстановлено {tokens_to_restore} burst токенов")
            else:
                # Ждем минимальное время только если нет токенов
                wait_time = (config.min_interval_ms / 1000) - time_since_last
                logger.debug(f"{api_name}: Ждем {wait_time:.2f}с для восстановления burst токенов")
                await asyncio.sleep(wait_time)
                self.burst_tokens[api_name] = 1

        # Регистрируем запрос
        self.last_request_times[api_name] = current_time
        self.request_counts[api_name].append(current_time)
        self.burst_tokens[api_name] -= 1

        logger.debug(f"{api_name}: Запрос разрешен. Burst токенов: {self.burst_tokens[api_name]}")

    async def handle_429_error(self, api_name: str, attempt: int = 0) -> None:
        """УЛУЧШЕННАЯ обработка 429 ошибки с экспоненциальной задержкой и автопаузой

        Args:
            api_name: Название API
            attempt: Номер попытки (0-based)

        """
        config = self.CONFIGS.get(api_name, self.CONFIGS["wb_general"])

        # Сбрасываем burst токены
        self.burst_tokens[api_name] = 0

        # Очищаем историю запросов для сброса лимитов
        self.request_counts[api_name] = []

        # КРИТИЧНО: Экспоненциальная задержка 2^attempt
        base_wait = config.retry_delay_base
        exponential_multiplier = min(2**attempt, 8)  # Максимум 8x
        wait_time = base_wait * exponential_multiplier + (attempt * config.retry_delay_multiplier)

        # КРИТИЧНО: Максимальная задержка 20 минут
        wait_time = min(wait_time, 1200)

        logger.error(
            f"🚨 {api_name}: 429 Too Many Requests, экспоненциальная задержка {wait_time}с (попытка {attempt + 1}, множитель {exponential_multiplier}x)"
        )

        # КРИТИЧНО: Если много попыток подряд, увеличиваем паузу
        if attempt >= 3:
            extra_wait = 300  # +5 минут за каждые 3+ попытки
            logger.error(f"⚠️ {api_name}: Частые 429 ошибки, дополнительная пауза {extra_wait}с")
            wait_time += extra_wait

        await asyncio.sleep(wait_time)

        # Восстанавливаем burst токены после ожидания
        self.burst_tokens[api_name] = config.burst_limit

    def get_api_stats(self, api_name: str) -> dict:
        """Получение статистики использования API"""
        current_time = time.time()
        minute_ago = current_time - 60

        recent_requests = [t for t in self.request_counts[api_name] if t > minute_ago]

        config = self.CONFIGS.get(api_name, self.CONFIGS["wb_general"])

        return {
            "api_name": api_name,
            "requests_last_minute": len(recent_requests),
            "requests_per_minute_limit": config.requests_per_minute,
            "burst_tokens_remaining": self.burst_tokens.get(api_name, 0),
            "burst_limit": config.burst_limit,
            "last_request_time": self.last_request_times.get(api_name),
            "min_interval_ms": config.min_interval_ms,
        }


# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter()


async def with_rate_limit(api_name: str):
    """Декоратор-функция для применения rate limiting к API запросам

    Usage:
        await with_rate_limit('wb_advertising')
        # ваш API запрос здесь
    """
    await rate_limiter.wait_for_rate_limit(api_name)


def get_rate_limit_stats() -> dict:
    """Получение статистики по всем API"""
    return {
        api_name: rate_limiter.get_api_stats(api_name) for api_name in rate_limiter.CONFIGS.keys()
    }
