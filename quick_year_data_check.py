#!/usr/bin/env python3
"""
БЫСТРАЯ ПРОВЕРКА ДОСТУПНОСТИ ГОДОВЫХ ДАННЫХ
Краткий анализ что реально доступно по API
"""

import asyncio
import logging
from api_chunking import ChunkedAPIManager
import api_clients_main as api_clients

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def quick_api_test():
    """Быстрый тест доступности данных"""

    logger.info("⚡ БЫСТРАЯ ПРОВЕРКА ДОСТУПНОСТИ ДАННЫХ ПО API")
    logger.info("=" * 60)

    chunked_api = ChunkedAPIManager(api_clients)

    # Ключевые тестовые периоды
    test_periods = [
        ("2024-01-01", "2024-01-31", "2024 январь"),
        ("2025-01-01", "2025-01-31", "2025 январь"),
        ("2025-04-01", "2025-04-30", "2025 апрель (известен)")
    ]

    logger.info("🟣 WB API - КРАТКИЙ ТЕСТ:")

    for date_from, date_to, description in test_periods:
        logger.info(f"\n📅 {description}: {date_from} → {date_to}")

        try:
            # Быстрый тест Sales API
            sales_data = await chunked_api.get_wb_sales_chunked(date_from, date_to)
            sales_count = len(sales_data) if sales_data else 0

            if sales_count > 0:
                # Анализируем даты в первых записях
                sample_dates = []
                sample_sum = 0
                for record in sales_data[:5]:
                    raw_date = record.get('date', '')
                    parsed_date = raw_date.split('T')[0] if 'T' in raw_date else raw_date[:10]
                    sample_dates.append(parsed_date)
                    sample_sum += record.get('forPay', 0) or 0

                date_range = f"{min(sample_dates)} → {max(sample_dates)}" if sample_dates else "N/A"

                logger.info(f"   ✅ Данные: {sales_count} записей")
                logger.info(f"   📊 Диапазон: {date_range}")
                logger.info(f"   💰 Сумма (5 записей): {sample_sum:,.0f} ₽")

                # Проверяем соответствие запрошенному периоду
                if sample_dates:
                    in_range = sum(1 for d in sample_dates if date_from <= d <= date_to)
                    logger.info(f"   🎯 В периоде: {in_range}/{len(sample_dates)}")
            else:
                logger.info(f"   ❌ Нет данных")

        except Exception as e:
            logger.error(f"   ❌ Ошибка: {e}")

        await asyncio.sleep(3)

    logger.info(f"\n🟦 OZON API - КРАТКИЙ ТЕСТ:")

    for date_from, date_to, description in test_periods:
        logger.info(f"\n📅 {description}: {date_from} → {date_to}")

        try:
            # Быстрый тест FBS API
            fbs_data = await chunked_api.get_ozon_fbs_chunked(date_from, date_to)
            fbs_count = len(fbs_data) if fbs_data else 0

            if fbs_count > 0:
                # Анализируем типы операций
                operations = {}
                revenue_sum = 0
                for record in fbs_data[:10]:
                    op_type = record.get('operation_type', 'unknown')
                    operations[op_type] = operations.get(op_type, 0) + 1
                    if op_type == 'OperationAgentDeliveredToCustomer':
                        revenue_sum += record.get('accruals_for_sale', 0) or 0

                logger.info(f"   ✅ Данные: {fbs_count} транзакций")
                logger.info(f"   📊 Операций: {len(operations)} типов")
                logger.info(f"   💰 Доставлено (10 записей): {revenue_sum:,.0f} ₽")
            else:
                logger.info(f"   ❌ Нет данных")

        except Exception as e:
            logger.error(f"   ❌ Ошибка: {e}")

        await asyncio.sleep(2)

    # Выводы на основе предыдущих тестов
    logger.info(f"\n" + "=" * 60)
    logger.info("📋 ВЫВОДЫ НА ОСНОВЕ ПОЛУЧЕННЫХ ДАННЫХ:")
    logger.info("")

    logger.info("🟣 WB API:")
    logger.info("   ✅ Технически работает для любых дат")
    logger.info("   ⚠️  НО: возвращает данные только за апрель-сентябрь 2025")
    logger.info("   📊 При запросе 2024 или январь 2025 → получаем апрель-сентябрь 2025")
    logger.info("   💡 Фактические данные: ~425,436₽ (forPay) за апрель-сентябрь")
    logger.info("")

    logger.info("🟦 OZON API:")
    logger.info("   ❌ Проблемы с доступом к данным")
    logger.info("   🚫 400 ошибки при запросах транзакций")
    logger.info("   ⚠️  Возможно требует настройки доступов")
    logger.info("")

    logger.info("🎯 ПРАКТИЧЕСКИЕ ВОЗМОЖНОСТИ:")
    logger.info("")
    logger.info("   📅 МАКСИМАЛЬНЫЙ РЕАЛЬНЫЙ ПЕРИОД:")
    logger.info("      WB: 2025-04-03 → 2025-09-26 (~176 дней)")
    logger.info("      Ozon: Недоступно (проблемы API)")
    logger.info("")
    logger.info("   💰 ФАКТИЧЕСКИЕ ЦИФРЫ ЗА ДОСТУПНЫЙ ПЕРИОД:")
    logger.info("      WB выручка (forPay): ~425,436 ₽")
    logger.info("      WB заказы (priceWithDisc): ~723,738 ₽")
    logger.info("      WB продаж: 360 записей")
    logger.info("      WB заказов: 607 записей")
    logger.info("")
    logger.info("   📊 ПРОЕКЦИЯ НА ГОД (если экстраполировать):")
    # 176 дней = 425,436₽ → 365 дней = ?
    days_available = 176
    wb_revenue = 425436
    wb_orders = 723738

    year_revenue = (wb_revenue / days_available) * 365
    year_orders = (wb_orders / days_available) * 365

    logger.info(f"      WB год выручка: ~{year_revenue:,.0f} ₽")
    logger.info(f"      WB год заказы: ~{year_orders:,.0f} ₽")
    logger.info(f"      (на основе {days_available} дней данных)")
    logger.info("")

    logger.info("✅ ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
    logger.info("   🔧 Год технически ВОЗМОЖЕН для WB")
    logger.info("   ⚠️  Но данные ограничены апрель-сентябрь 2025")
    logger.info("   💡 Для полного года нужны дополнительные источники")
    logger.info("   🛠️  Ozon требует исправления доступов к API")

if __name__ == "__main__":
    asyncio.run(quick_api_test())