"""
Утилиты для мониторинга и отладки rate limiter
"""

import asyncio
import logging
from typing import Dict, Any
from rate_limiter import get_rate_limit_stats, rate_limiter

logger = logging.getLogger(__name__)


async def monitor_api_usage() -> str:
    """Получение детального отчета об использовании API"""
    stats = get_rate_limit_stats()

    report = "📊 **Rate Limiter Status Report**\n\n"

    for api_name, stat in stats.items():
        if stat['requests_last_minute'] > 0 or api_name in ['wb_advertising', 'ozon_general']:
            report += f"🔹 **{api_name.upper()}**\n"
            report += f"   • Запросы: {stat['requests_last_minute']}/{stat['requests_per_minute_limit']} req/min\n"
            report += f"   • Burst токены: {stat['burst_tokens_remaining']}/{stat['burst_limit']}\n"
            report += f"   • Мин. интервал: {stat['min_interval_ms']}ms\n"

            # Процент использования
            usage_percent = (stat['requests_last_minute'] / stat['requests_per_minute_limit']) * 100
            if usage_percent > 80:
                report += f"   • ⚠️ Высокая нагрузка: {usage_percent:.1f}%\n"
            elif usage_percent > 50:
                report += f"   • 🟡 Средняя нагрузка: {usage_percent:.1f}%\n"
            else:
                report += f"   • ✅ Низкая нагрузка: {usage_percent:.1f}%\n"

            # Оставшиеся burst токены
            burst_percent = (stat['burst_tokens_remaining'] / stat['burst_limit']) * 100
            if burst_percent < 20:
                report += f"   • 🔴 Мало burst токенов: {burst_percent:.0f}%\n"

            report += "\n"

    return report


async def simulate_rate_limiting_test() -> str:
    """Тестирование rate limiter с симуляцией запросов"""
    test_results = []

    test_results.append("🧪 **Rate Limiter Testing**\n")

    # Тест 1: Проверка работы с нормальными интервалами
    test_results.append("**Тест 1: Нормальные интервалы**")
    try:
        from rate_limiter import with_rate_limit

        start_time = asyncio.get_event_loop().time()
        await with_rate_limit('wb_advertising')
        end_time = asyncio.get_event_loop().time()

        wait_time = (end_time - start_time) * 1000
        test_results.append(f"✅ Задержка: {wait_time:.1f}ms")

    except Exception as e:
        test_results.append(f"❌ Ошибка: {e}")

    # Тест 2: Проверка burst токенов
    test_results.append("\n**Тест 2: Burst токены**")
    try:
        initial_stats = get_rate_limit_stats()['wb_advertising']

        # Делаем несколько быстрых запросов
        for i in range(3):
            await with_rate_limit('wb_advertising')

        final_stats = get_rate_limit_stats()['wb_advertising']

        burst_used = initial_stats['burst_tokens_remaining'] - final_stats['burst_tokens_remaining']
        test_results.append(f"✅ Использовано burst токенов: {burst_used}")
        test_results.append(f"✅ Осталось: {final_stats['burst_tokens_remaining']}/{final_stats['burst_limit']}")

    except Exception as e:
        test_results.append(f"❌ Ошибка: {e}")

    return "\n".join(test_results)


async def reset_rate_limiter_stats() -> str:
    """Сброс статистики rate limiter"""
    try:
        # Сбрасываем счетчики
        rate_limiter.request_counts.clear()
        rate_limiter.last_request_times.clear()

        # Восстанавливаем burst токены
        for api_name, config in rate_limiter.CONFIGS.items():
            rate_limiter.burst_tokens[api_name] = config.burst_limit

        logger.info("Rate limiter statistics reset")
        return "✅ Статистика rate limiter сброшена"

    except Exception as e:
        logger.error(f"Ошибка сброса rate limiter: {e}")
        return f"❌ Ошибка сброса: {e}"


def get_rate_limiter_recommendations() -> str:
    """Получение рекомендаций по оптимизации rate limiting"""
    stats = get_rate_limit_stats()
    recommendations = []

    recommendations.append("💡 **Рекомендации по Rate Limiting**\n")

    for api_name, stat in stats.items():
        if stat['requests_last_minute'] > 0:
            usage_percent = (stat['requests_last_minute'] / stat['requests_per_minute_limit']) * 100

            if usage_percent > 90:
                recommendations.append(f"🔴 **{api_name}**: Критическая нагрузка! Снизите частоту запросов")
            elif usage_percent > 70:
                recommendations.append(f"🟡 **{api_name}**: Высокая нагрузка. Рассмотрите кеширование")
            elif usage_percent > 50:
                recommendations.append(f"🟢 **{api_name}**: Умеренная нагрузка. Можно увеличить частоту")

            # Проверка burst токенов
            burst_percent = (stat['burst_tokens_remaining'] / stat['burst_limit']) * 100
            if burst_percent < 30:
                recommendations.append(f"⚠️ **{api_name}**: Мало burst токенов. Добавьте паузы между запросами")

    if len(recommendations) == 1:  # Только заголовок
        recommendations.append("✅ Все API работают в оптимальном режиме")

    return "\n".join(recommendations)


if __name__ == "__main__":
    # Тестовый запуск
    async def main():
        print(await monitor_api_usage())
        print(await simulate_rate_limiting_test())
        print(get_rate_limiter_recommendations())

    asyncio.run(main())