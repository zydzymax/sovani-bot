#!/usr/bin/env python3
"""
АНАЛИЗ ВОЗМОЖНОСТЕЙ OZON API
Определяем максимальные периоды и оптимальные задержки для Ozon
"""

import asyncio
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_ozon_api_capabilities():
    """Анализ возможностей Ozon API"""

    logger.info("🟦 АНАЛИЗ ВОЗМОЖНОСТЕЙ OZON API")
    logger.info("=" * 60)

    # Параметры Ozon API из системы
    OZON_CHUNK_SIZES = {
        'ozon_fbo': 60,  # дней на чанк
        'ozon_fbs': 60,  # дней на чанк
        'ozon_advertising': 60  # дней на чанк
    }

    logger.info("📋 ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ OZON API:")
    logger.info("   FBO API: 60 дней на чанк")
    logger.info("   FBS API: 60 дней на чанк")
    logger.info("   Advertising API: 60 дней на чанк")
    logger.info("   Rate Limit: более мягкий чем WB")
    logger.info("")

    # Анализ периодов для Ozon
    periods = [
        (365, "Полный год"),
        (270, "9 месяцев"),
        (180, "6 месяцев"),
        (120, "4 месяца"),
        (90, "3 месяца"),
        (60, "2 месяца"),
        (30, "1 месяц")
    ]

    logger.info("🔢 РАСЧЕТЫ ДЛЯ OZON API:")
    logger.info("")

    # Для основных транзакций используем FBS (он содержит все данные)
    chunk_size = OZON_CHUNK_SIZES['ozon_fbs']
    apis_per_chunk = 1  # Только FBS API (FBO дублируется в FBS)

    results = []

    for days, description in periods:
        chunks_needed = (days + chunk_size - 1) // chunk_size

        # Ozon более лояльный к запросам
        base_delay = 2.0  # секунды между запросами

        # Адаптивная задержка для Ozon
        if days > 300:
            delay = 4.0  # Для года
        elif days > 180:
            delay = 3.0  # Для полугода
        elif days > 90:
            delay = 2.5  # Для квартала
        else:
            delay = 2.0  # Для месяца

        total_requests = chunks_needed * apis_per_chunk
        processing_time_seconds = total_requests * delay
        processing_time_minutes = processing_time_seconds / 60

        # Оценка сложности для Ozon
        if chunks_needed <= 2:
            complexity = "ПРОСТАЯ"
        elif chunks_needed <= 4:
            complexity = "СРЕДНЯЯ"
        elif chunks_needed <= 8:
            complexity = "СЛОЖНАЯ"
        else:
            complexity = "ОЧЕНЬ СЛОЖНАЯ"

        results.append({
            'days': days,
            'description': description,
            'chunks': chunks_needed,
            'requests': total_requests,
            'delay': delay,
            'time_minutes': processing_time_minutes,
            'complexity': complexity
        })

        logger.info(f"📅 {description:15s} ({days:3d} дней):")
        logger.info(f"   Чанков: {chunks_needed:2d}")
        logger.info(f"   Запросов: {total_requests:2d}")
        logger.info(f"   Задержка: {delay:.1f}s")
        logger.info(f"   Время: {processing_time_minutes:5.1f} мин")
        logger.info(f"   Сложность: {complexity}")
        logger.info("")

    # Сравнение с WB
    logger.info("⚖️  СРАВНЕНИЕ OZON vs WB:")
    logger.info("")

    # Расчет для года
    year_result = next(r for r in results if r['days'] == 365)

    # WB для года (обновленные параметры)
    wb_chunks_year = (365 + 45 - 1) // 45  # 9 чанков
    wb_requests_year = wb_chunks_year * 2  # Sales + Orders
    wb_delay_year = 8.0  # Новая задержка для года
    wb_time_year = (wb_requests_year * wb_delay_year) / 60

    logger.info(f"📊 ГОД (365 дней):")
    logger.info(f"   OZON: {year_result['chunks']} чанков, {year_result['requests']} запросов, {year_result['time_minutes']:.1f} мин")
    logger.info(f"   WB:   {wb_chunks_year} чанков, {wb_requests_year} запросов, {wb_time_year:.1f} мин")
    logger.info("")

    if year_result['time_minutes'] < wb_time_year:
        logger.info("✅ OZON БЫСТРЕЕ для годовых периодов!")
        ozon_advantage = wb_time_year - year_result['time_minutes']
        logger.info(f"   Преимущество: {ozon_advantage:.1f} минут")
    else:
        logger.info("⚠️  WB быстрее для годовых периодов")

    logger.info("")

    # Рекомендации по задержкам для Ozon
    logger.info("🎯 РЕКОМЕНДУЕМЫЕ ЗАДЕРЖКИ ДЛЯ OZON:")
    logger.info("")
    for result in results:
        if result['complexity'] == "ПРОСТАЯ":
            status = "✅ ОПТИМАЛЬНО"
        elif result['complexity'] == "СРЕДНЯЯ":
            status = "🔶 ХОРОШО"
        elif result['complexity'] == "СЛОЖНАЯ":
            status = "⚠️  ОСТОРОЖНО"
        else:
            status = "❌ ИЗБЕГАТЬ"

        logger.info(f"   {result['description']:15s}: {result['delay']:.1f}s - {status}")

    logger.info("")

    # Максимальные возможности
    logger.info("🚀 МАКСИМАЛЬНЫЕ ВОЗМОЖНОСТИ:")
    logger.info("")
    logger.info("   📅 OZON Максимальный период: НЕОГРАНИЧЕН (теоретически)")
    logger.info("   📅 OZON Рекомендуемый максимум: 365 дней (год)")
    logger.info("   📅 OZON Оптимальный период: 120 дней (4 месяца)")
    logger.info("")
    logger.info("   ⚡ Преимущества OZON API:")
    logger.info("     • Больше данных на чанк (60 vs 45 дней)")
    logger.info("     • Мягче rate limiting")
    logger.info("     • Меньше API вызовов (только FBS)")
    logger.info("     • Лучше для больших периодов")

    logger.info("")

    # Итоговые рекомендации
    logger.info("✅ ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
    logger.info("")
    logger.info("   🟦 OZON:")
    logger.info(f"     Максимум: {year_result['days']} дней ({year_result['time_minutes']:.1f} мин)")
    logger.info(f"     Оптимум: 120 дней (2 чанка, ~{results[3]['time_minutes']:.1f} мин)")
    logger.info("")
    logger.info("   🟣 WB:")
    logger.info(f"     Максимум: 365 дней ({wb_time_year:.1f} мин)")
    logger.info(f"     Оптимум: 90 дней (2 чанка, ~{(2*2*3.5)/60:.1f} мин)")

    return results

def generate_optimized_delays_config():
    """Генерация оптимизированной конфигурации задержек"""

    logger.info("\n🔧 ОПТИМИЗИРОВАННАЯ КОНФИГУРАЦИЯ ЗАДЕРЖЕК")
    logger.info("=" * 60)

    config = {
        'wb_delays': {
            'year_plus': {'days': '300+', 'delay': 8.0, 'description': 'Годовые периоды'},
            'half_year': {'days': '180-300', 'delay': 5.0, 'description': 'Полугодовые периоды'},
            'quarter': {'days': '90-180', 'delay': 3.5, 'description': 'Квартальные периоды'},
            'month': {'days': '30-90', 'delay': 2.5, 'description': 'Месячные периоды'},
            'short': {'days': '1-30', 'delay': 2.0, 'description': 'Короткие периоды'}
        },
        'ozon_delays': {
            'year_plus': {'days': '300+', 'delay': 4.0, 'description': 'Годовые периоды'},
            'half_year': {'days': '180-300', 'delay': 3.0, 'description': 'Полугодовые периоды'},
            'quarter': {'days': '90-180', 'delay': 2.5, 'description': 'Квартальные периоды'},
            'short': {'days': '1-90', 'delay': 2.0, 'description': 'Короткие периоды'}
        }
    }

    logger.info("📋 WB API ЗАДЕРЖКИ:")
    for key, value in config['wb_delays'].items():
        logger.info(f"   {value['description']:20s}: {value['delay']:.1f}s ({value['days']} дней)")

    logger.info("")
    logger.info("📋 OZON API ЗАДЕРЖКИ:")
    for key, value in config['ozon_delays'].items():
        logger.info(f"   {value['description']:20s}: {value['delay']:.1f}s ({value['days']} дней)")

    logger.info("")
    logger.info("💡 ОБЩИЕ ПРИНЦИПЫ:")
    logger.info("   • Чем больше период - тем больше задержка")
    logger.info("   • OZON более лояльный - меньше задержки")
    logger.info("   • WB требует больше осторожности")
    logger.info("   • Год возможен, но требует терпения")

    return config

if __name__ == "__main__":
    # Анализируем Ozon
    ozon_results = analyze_ozon_api_capabilities()

    # Генерируем конфигурацию
    config = generate_optimized_delays_config()