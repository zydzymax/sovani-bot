#!/usr/bin/env python3
"""РАСЧЕТ МАКСИМАЛЬНОГО ПЕРИОДА НА ГОД
Анализ теоретических возможностей для обработки годового периода
"""

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def calculate_year_processing():
    """Расчет обработки годового периода"""
    logger.info("📊 РАСЧЕТ ОБРАБОТКИ ГОДОВОГО ПЕРИОДА")
    logger.info("=" * 60)

    # Параметры системы
    CHUNK_SIZE_DAYS = 45  # Размер чанка для WB API
    DELAY_BETWEEN_REQUESTS = 3  # Секунды между запросами
    APIS_PER_CHUNK = 2  # Sales + Orders API

    # Периоды для анализа
    periods = [
        (365, "Полный год"),
        (270, "9 месяцев"),
        (180, "6 месяцев"),
        (90, "3 месяца (квартал)"),
        (45, "1.5 месяца"),
        (30, "1 месяц"),
    ]

    logger.info("🔢 ТЕОРЕТИЧЕСКИЕ РАСЧЕТЫ:")
    logger.info("")

    results = []

    for days, description in periods:
        # Расчет количества чанков
        chunks_needed = (days + CHUNK_SIZE_DAYS - 1) // CHUNK_SIZE_DAYS

        # Расчет времени обработки
        total_requests = chunks_needed * APIS_PER_CHUNK
        processing_time_seconds = total_requests * DELAY_BETWEEN_REQUESTS
        processing_time_minutes = processing_time_seconds / 60
        processing_time_hours = processing_time_minutes / 60

        # Оценка сложности
        if chunks_needed <= 2:
            complexity = "ПРОСТАЯ"
        elif chunks_needed <= 5:
            complexity = "СРЕДНЯЯ"
        elif chunks_needed <= 10:
            complexity = "СЛОЖНАЯ"
        else:
            complexity = "ОЧЕНЬ СЛОЖНАЯ"

        results.append(
            {
                "days": days,
                "description": description,
                "chunks": chunks_needed,
                "requests": total_requests,
                "time_minutes": processing_time_minutes,
                "time_hours": processing_time_hours,
                "complexity": complexity,
            }
        )

        logger.info(f"📅 {description:20s} ({days:3d} дней):")
        logger.info(f"   Чанков: {chunks_needed:2d}")
        logger.info(f"   Запросов: {total_requests:2d}")
        logger.info(
            f"   Время: {processing_time_minutes:5.1f} мин ({processing_time_hours:4.1f} ч)"
        )
        logger.info(f"   Сложность: {complexity}")
        logger.info("")

    # Анализ ограничений
    logger.info("⚠️  ПРАКТИЧЕСКИЕ ОГРАНИЧЕНИЯ:")
    logger.info("")

    # Rate Limiting
    logger.info("🚦 RATE LIMITING:")
    max_requests_per_hour = 3600 / DELAY_BETWEEN_REQUESTS  # 1200 запросов/час
    year_result = next(r for r in results if r["days"] == 365)

    logger.info(f"   Теоретический лимит: {max_requests_per_hour:.0f} запросов/час")
    logger.info(f"   Для года нужно: {year_result['requests']} запросов")
    logger.info(f"   Минимальное время: {year_result['time_hours']:.1f} часа")
    logger.info("")

    # API Stability
    logger.info("🔧 СТАБИЛЬНОСТЬ API:")
    failure_rate = 0.05  # 5% запросов могут упасть
    year_expected_failures = year_result["requests"] * failure_rate
    retry_overhead = year_expected_failures * 2  # Каждый retry удваивает время

    logger.info(f"   Ожидаемых сбоев (5%): {year_expected_failures:.0f}")
    logger.info(
        f"   Дополнительное время на retry: {retry_overhead * DELAY_BETWEEN_REQUESTS / 60:.1f} мин"
    )
    logger.info("")

    # Memory and Storage
    logger.info("💾 ПАМЯТЬ И ХРАНЕНИЕ:")
    avg_records_per_chunk = 1000  # Примерное количество записей на чанк
    year_total_records = year_result["chunks"] * avg_records_per_chunk
    memory_per_record = 1024  # bytes
    total_memory_mb = (year_total_records * memory_per_record) / (1024 * 1024)

    logger.info(f"   Ожидаемых записей: {year_total_records:,}")
    logger.info(f"   Требуемая память: ~{total_memory_mb:.0f} MB")
    logger.info("")

    # Рекомендации
    logger.info("🎯 РЕКОМЕНДАЦИИ ПО ПЕРИОДАМ:")
    logger.info("")

    for result in results:
        if result["complexity"] == "ПРОСТАЯ":
            status = "✅ РЕКОМЕНДУЕТСЯ"
        elif result["complexity"] == "СРЕДНЯЯ":
            status = "🔶 ДОПУСТИМО"
        elif result["complexity"] == "СЛОЖНАЯ":
            status = "⚠️  ОСТОРОЖНО"
        else:
            status = "❌ НЕ РЕКОМЕНДУЕТСЯ"

        logger.info(f"   {result['description']:20s}: {status}")

    logger.info("")

    # Альтернативные стратегии
    logger.info("🔄 АЛЬТЕРНАТИВНЫЕ СТРАТЕГИИ ДЛЯ ГОДА:")
    logger.info("")
    logger.info("   1️⃣  ПОЭТАПНАЯ ОБРАБОТКА:")
    logger.info("      • Разбить год на 4 квартала (90 дней каждый)")
    logger.info("      • Обрабатывать по кварталу с перерывами")
    logger.info("      • Общее время: 4 × 6 мин = 24 минуты")
    logger.info("")
    logger.info("   2️⃣  МЕСЯЧНАЯ ОБРАБОТКА:")
    logger.info("      • Обрабатывать по месяцу (30 дней)")
    logger.info("      • 12 месяцев × 2 минуты = 24 минуты")
    logger.info("      • Меньше нагрузки на API")
    logger.info("")
    logger.info("   3️⃣  ГИБРИДНЫЙ ПОДХОД:")
    logger.info("      • API для последних 3-6 месяцев")
    logger.info("      • Ручные выгрузки для старых данных")
    logger.info("      • Кэширование результатов")
    logger.info("")

    # Финальные рекомендации
    logger.info("✅ ФИНАЛЬНЫЕ РЕКОМЕНДАЦИИ:")
    logger.info("")
    logger.info("   📅 МАКСИМАЛЬНЫЙ БЕЗОПАСНЫЙ ПЕРИОД: 180 дней (6 месяцев)")
    logger.info(f"      • {results[2]['chunks']} чанков")
    logger.info(f"      • ~{results[2]['time_minutes']:.0f} минут обработки")
    logger.info("      • Низкий риск сбоев")
    logger.info("")
    logger.info("   📅 ОПТИМАЛЬНЫЙ ПЕРИОД: 90 дней (3 месяца)")
    logger.info(f"      • {results[3]['chunks']} чанков")
    logger.info(f"      • ~{results[3]['time_minutes']:.0f} минут обработки")
    logger.info("      • Отличный баланс данных/времени")
    logger.info("")
    logger.info("   📅 ДЛЯ ГОДОВЫХ ОТЧЕТОВ:")
    logger.info("      • 4 запроса по 90 дней с интервалом")
    logger.info("      • Или API + ручные выгрузки")
    logger.info("      • Общее время: ~30-40 минут")

    return results


if __name__ == "__main__":
    calculate_year_processing()
