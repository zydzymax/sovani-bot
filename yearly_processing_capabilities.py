#!/usr/bin/env python3
"""
ИТОГОВЫЙ ОТЧЕТ: ВОЗМОЖНОСТИ ОБРАБОТКИ ГОДОВЫХ ДАННЫХ
Сводный анализ после оптимизации задержек
"""

import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_yearly_capabilities_report():
    """Генерация итогового отчета по возможностям"""

    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ: ВОЗМОЖНОСТИ ОБРАБОТКИ ГОДОВЫХ ДАННЫХ")
    logger.info("=" * 70)
    logger.info("После оптимизации задержек для безопасной загрузки")
    logger.info("")

    # Параметры после оптимизации
    wb_config = {
        'chunk_size': 45,
        'apis_per_chunk': 2,  # Sales + Orders
        'delays': {
            'year': 8.0,
            'half_year': 5.0,
            'quarter': 3.5,
            'month': 2.5,
            'short': 2.0
        }
    }

    ozon_config = {
        'chunk_size': 60,
        'apis_per_chunk': 1,  # Только FBS (включает все данные)
        'delays': {
            'year': 4.0,
            'half_year': 3.0,
            'quarter': 2.5,
            'short': 2.0
        }
    }

    # Анализ различных периодов
    periods = [
        (365, "Полный год", "year"),
        (270, "9 месяцев", "half_year"),
        (180, "Полугодие", "half_year"),
        (90, "Квартал", "quarter"),
        (60, "2 месяца", "short"),
        (30, "Месяц", "short")
    ]

    logger.info("🟣 WILDBERRIES API (после оптимизации):")
    logger.info("=" * 50)

    wb_results = []
    for days, description, delay_type in periods:
        chunks = (days + wb_config['chunk_size'] - 1) // wb_config['chunk_size']
        requests = chunks * wb_config['apis_per_chunk']
        delay = wb_config['delays'][delay_type]
        time_minutes = (requests * delay) / 60

        # Оценка надежности
        if time_minutes < 1:
            reliability = "ОТЛИЧНО"
        elif time_minutes < 3:
            reliability = "ХОРОШО"
        elif time_minutes < 5:
            reliability = "ДОПУСТИМО"
        else:
            reliability = "ОСТОРОЖНО"

        wb_results.append({
            'days': days,
            'description': description,
            'chunks': chunks,
            'requests': requests,
            'delay': delay,
            'time_minutes': time_minutes,
            'reliability': reliability
        })

        logger.info(f"📅 {description:12s} ({days:3d} дней):")
        logger.info(f"   Чанков: {chunks:2d} | Запросов: {requests:2d} | Задержка: {delay:.1f}s")
        logger.info(f"   Время: {time_minutes:4.1f} мин | Надежность: {reliability}")
        logger.info("")

    logger.info("🟦 OZON API (после оптимизации):")
    logger.info("=" * 50)

    ozon_results = []
    for days, description, delay_type in periods:
        chunks = (days + ozon_config['chunk_size'] - 1) // ozon_config['chunk_size']
        requests = chunks * ozon_config['apis_per_chunk']
        delay = ozon_config['delays'][delay_type]
        time_minutes = (requests * delay) / 60

        # Оценка надежности
        if time_minutes < 0.5:
            reliability = "ОТЛИЧНО"
        elif time_minutes < 1:
            reliability = "ХОРОШО"
        elif time_minutes < 2:
            reliability = "ДОПУСТИМО"
        else:
            reliability = "ОСТОРОЖНО"

        ozon_results.append({
            'days': days,
            'description': description,
            'chunks': chunks,
            'requests': requests,
            'delay': delay,
            'time_minutes': time_minutes,
            'reliability': reliability
        })

        logger.info(f"📅 {description:12s} ({days:3d} дней):")
        logger.info(f"   Чанков: {chunks:2d} | Запросов: {requests:2d} | Задержка: {delay:.1f}s")
        logger.info(f"   Время: {time_minutes:4.1f} мин | Надежность: {reliability}")
        logger.info("")

    # Сравнительная таблица
    logger.info("⚖️  СРАВНИТЕЛЬНАЯ ТАБЛИЦА:")
    logger.info("=" * 70)
    logger.info(f"{'Период':12s} | {'WB время':8s} | {'Ozon время':9s} | {'Победитель':10s}")
    logger.info("-" * 70)

    for i, (days, description, _) in enumerate(periods):
        wb_time = wb_results[i]['time_minutes']
        ozon_time = ozon_results[i]['time_minutes']

        if ozon_time < wb_time:
            winner = "OZON"
            advantage = wb_time - ozon_time
        else:
            winner = "WB"
            advantage = ozon_time - wb_time

        logger.info(f"{description:12s} | {wb_time:6.1f} мин | {ozon_time:7.1f} мин | {winner:10s}")

    logger.info("")

    # Ключевые выводы
    logger.info("🎯 КЛЮЧЕВЫЕ ВЫВОДЫ:")
    logger.info("")

    # Годовой период
    wb_year = next(r for r in wb_results if r['days'] == 365)
    ozon_year = next(r for r in ozon_results if r['days'] == 365)

    logger.info("📅 ГОДОВОЙ ПЕРИОД (365 дней):")
    logger.info(f"   WB:   {wb_year['chunks']} чанков, {wb_year['time_minutes']:.1f} мин ({wb_year['reliability']})")
    logger.info(f"   Ozon: {ozon_year['chunks']} чанков, {ozon_year['time_minutes']:.1f} мин ({ozon_year['reliability']})")

    if ozon_year['time_minutes'] < wb_year['time_minutes']:
        logger.info(f"   🏆 OZON быстрее на {wb_year['time_minutes'] - ozon_year['time_minutes']:.1f} минут")

    logger.info("")

    # Рекомендации
    logger.info("✅ ПРАКТИЧЕСКИЕ РЕКОМЕНДАЦИИ:")
    logger.info("")

    logger.info("🟣 ДЛЯ WILDBERRIES:")
    logger.info("   📅 Максимум: 365 дней (возможно, но медленно)")
    logger.info("   📅 Оптимум: 90 дней (быстро и надежно)")
    logger.info("   📅 Ежедневно: 30 дней (мгновенно)")
    logger.info("")

    logger.info("🟦 ДЛЯ OZON:")
    logger.info("   📅 Максимум: 365 дней (легко и быстро)")
    logger.info("   📅 Оптимум: 120 дней (практически мгновенно)")
    logger.info("   📅 Ежедневно: 60 дней (без задержек)")
    logger.info("")

    # Стратегии для разных случаев
    logger.info("🚀 СТРАТЕГИИ ИСПОЛЬЗОВАНИЯ:")
    logger.info("")

    logger.info("1️⃣  БЫСТРЫЕ ЕЖЕДНЕВНЫЕ ОТЧЕТЫ:")
    logger.info("   • WB: 30 дней (~0.2 мин)")
    logger.info("   • Ozon: 60 дней (~0.1 мин)")
    logger.info("   • Общее время: ~0.3 минуты")
    logger.info("")

    logger.info("2️⃣  КВАРТАЛЬНЫЕ ОТЧЕТЫ:")
    logger.info("   • WB: 90 дней (~0.4 мин)")
    logger.info("   • Ozon: 90 дней (~0.1 мин)")
    logger.info("   • Общее время: ~0.5 минут")
    logger.info("")

    logger.info("3️⃣  ГОДОВЫЕ ОТЧЕТЫ:")
    logger.info("   Вариант A (прямо):")
    logger.info("   • WB: 365 дней (~2.4 мин)")
    logger.info("   • Ozon: 365 дней (~0.5 мин)")
    logger.info("   • Общее время: ~3 минуты")
    logger.info("")
    logger.info("   Вариант B (по кварталам):")
    logger.info("   • 4 × (WB 90 дней + Ozon 90 дней)")
    logger.info("   • 4 × 0.5 мин = 2 минуты")
    logger.info("   • Надежнее и с возможностью паузы")
    logger.info("")

    # Финальные рекомендации
    logger.info("🏆 ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
    logger.info("")
    logger.info("   ✅ ГОД ВОЗМОЖЕН для обеих платформ!")
    logger.info("   ✅ Ozon лучше для больших периодов")
    logger.info("   ✅ WB требует больше терпения, но тоже работает")
    logger.info("   ✅ Рекомендуется поэтапная обработка для максимальной надежности")
    logger.info("")

    logger.info("💡 ЗОЛОТОЕ ПРАВИЛО:")
    logger.info("   Чем больше период - тем больше задержка")
    logger.info("   Система автоматически выберет оптимальную задержку")
    logger.info("   Год обрабатывается ~3 минуты для обеих платформ")

    return {
        'wb_results': wb_results,
        'ozon_results': ozon_results,
        'year_wb_time': wb_year['time_minutes'],
        'year_ozon_time': ozon_year['time_minutes'],
        'total_year_time': wb_year['time_minutes'] + ozon_year['time_minutes']
    }

if __name__ == "__main__":
    report = generate_yearly_capabilities_report()