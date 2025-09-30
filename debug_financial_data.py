#!/usr/bin/env python3
"""
Диагностика проблем с финансовыми данными
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_financial_data():
    """Диагностика проблем с данными в финансовых отчетах"""
    try:
        from real_data_reports import RealDataFinancialReports

        logger.info("🔍 Диагностика финансовых данных за период 2025-01-01 - 2025-09-21")

        reports = RealDataFinancialReports()
        date_from = "2025-01-01"
        date_to = "2025-09-21"

        # Проверяем WB данные
        logger.info("\n📊 Проверка WB данных...")
        wb_data = await reports.get_real_wb_sales(date_from, date_to)

        logger.info(f"WB результаты:")
        logger.info(f"  Выручка: {wb_data.get('revenue', 0):,.2f} ₽")
        logger.info(f"  Единиц доставлено: {wb_data.get('units', 0)}")
        logger.info(f"  Заказов единиц: {wb_data.get('orders_units', 0)}")
        logger.info(f"  Сумма заказов: {wb_data.get('orders_revenue', 0):,.2f} ₽")
        logger.info(f"  Процент выкупа: {wb_data.get('buyout_rate', 0):.1f}%")
        logger.info(f"  Возвратов: {wb_data.get('returns_count', 0)}")

        # Анализируем сырые данные WB
        if 'sales_data' in wb_data:
            sales_data = wb_data['sales_data']
            logger.info(f"\n🔍 Анализ сырых данных WB ({len(sales_data)} записей):")

            # Считаем уникальные даты
            dates = set()
            realizations = 0
            returns = 0

            for sale in sales_data[:10]:  # Показываем первые 10 для примера
                date = sale.get('date', '')[:10]
                dates.add(date)

                if sale.get('isRealization'):
                    realizations += 1
                else:
                    returns += 1

                logger.info(f"  Пример записи: {sale.get('date', '')} - {sale.get('saleID', '')} - "
                          f"{'реализация' if sale.get('isRealization') else 'возврат'} - "
                          f"{sale.get('priceWithDisc', 0)} ₽")

            logger.info(f"  Уникальных дат: {len(dates)}")
            logger.info(f"  Реализаций: {realizations}")
            logger.info(f"  Возвратов: {returns}")

            if dates:
                sorted_dates = sorted(dates)
                logger.info(f"  Период данных: {sorted_dates[0]} - {sorted_dates[-1]}")

        # Проверяем Ozon данные
        logger.info("\n📊 Проверка Ozon данных...")
        ozon_data = await reports.get_real_ozon_sales(date_from, date_to)

        logger.info(f"Ozon результаты:")
        logger.info(f"  Выручка: {ozon_data.get('revenue', 0):,.2f} ₽")
        logger.info(f"  Единиц: {ozon_data.get('units', 0)}")
        logger.info(f"  Комиссия: {ozon_data.get('commission', 0):,.2f} ₽")

        # Проверяем chunked API напрямую
        logger.info("\n🔄 Проверка chunked API...")

        from api_chunking import ChunkedAPIManager
        import api_clients_main as api_clients

        chunked_api = ChunkedAPIManager(api_clients)

        # Тестируем небольшой период
        test_from = "2025-09-15"
        test_to = "2025-09-21"

        logger.info(f"Тестируем chunked API за период {test_from} - {test_to}")

        try:
            wb_chunked = await chunked_api.get_wb_sales_chunked(test_from, test_to)
            logger.info(f"WB chunked: {len(wb_chunked)} записей")

            if wb_chunked:
                logger.info(f"Первая запись: {wb_chunked[0]}")
        except Exception as e:
            logger.error(f"Ошибка WB chunked API: {e}")

        try:
            ozon_fbo = await chunked_api.get_ozon_fbo_chunked(test_from, test_to)
            ozon_fbs = await chunked_api.get_ozon_fbs_chunked(test_from, test_to)
            logger.info(f"Ozon FBO chunked: {len(ozon_fbo or [])} записей")
            logger.info(f"Ozon FBS chunked: {len(ozon_fbs or [])} записей")

            if ozon_fbo:
                logger.info(f"Первая FBO запись: {ozon_fbo[0]}")
            if ozon_fbs:
                logger.info(f"Первая FBS запись: {ozon_fbs[0]}")

        except Exception as e:
            logger.error(f"Ошибка Ozon chunked API: {e}")

        # Проверяем старый метод получения данных
        logger.info("\n📁 Проверка старого метода (файлы)...")

        try:
            # Пробуем старый download_wb_reports
            wb_reports = await api_clients.download_wb_reports()
            if wb_reports and wb_reports.get('sales'):
                with open(wb_reports['sales'], 'r', encoding='utf-8') as f:
                    import json
                    old_sales = json.load(f)
                logger.info(f"Старый метод WB: {len(old_sales)} записей")
            else:
                logger.info("Старый метод WB: нет данных")
        except Exception as e:
            logger.error(f"Ошибка старого метода WB: {e}")

        logger.info("\n✅ Диагностика завершена")

    except Exception as e:
        logger.error(f"❌ Ошибка диагностики: {e}")

if __name__ == "__main__":
    asyncio.run(debug_financial_data())