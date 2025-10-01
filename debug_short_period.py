#!/usr/bin/env python3
"""Диагностика данных за короткий период"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def debug_short_period():
    """Диагностика данных за короткий период"""
    try:
        from real_data_reports import RealDataFinancialReports

        # Тестируем последнюю неделю
        date_from = "2025-09-15"
        date_to = "2025-09-21"

        logger.info(f"🔍 Диагностика за короткий период: {date_from} - {date_to}")

        reports = RealDataFinancialReports()

        # Проверяем WB данные
        logger.info("\n📊 WB данные...")
        wb_data = await reports.get_real_wb_sales(date_from, date_to)

        logger.info("WB результаты:")
        logger.info(f"  Выручка: {wb_data.get('revenue', 0):,.2f} ₽")
        logger.info(f"  Единиц доставлено: {wb_data.get('units', 0)}")
        logger.info(f"  Заказов единиц: {wb_data.get('orders_units', 0)}")
        logger.info(f"  Процент выкупа: {wb_data.get('buyout_rate', 0):.1f}%")

        # Анализируем первые записи
        if wb_data.get("sales_data"):
            sales_data = wb_data["sales_data"]
            logger.info(f"\n🔍 Первые 5 записей WB ({len(sales_data)} всего):")

            for i, sale in enumerate(sales_data[:5]):
                logger.info(f"  {i+1}. Дата: {sale.get('date', '')[:19]}")
                logger.info(f"     Реализация: {sale.get('isRealization')}")
                logger.info(f"     Поставка: {sale.get('isSupply')}")
                logger.info(
                    f"     Цена: {sale.get('totalPrice', 0)} → {sale.get('priceWithDisc', 0)} ₽"
                )
                logger.info(f"     К доплате: {sale.get('forPay', 0)} ₽")

        # Проверяем Ozon данные
        logger.info("\n📊 Ozon данные...")
        ozon_data = await reports.get_real_ozon_sales(date_from, date_to)

        logger.info("Ozon результаты:")
        logger.info(f"  Выручка: {ozon_data.get('revenue', 0):,.2f} ₽")
        logger.info(f"  Единиц: {ozon_data.get('units', 0)}")

        # Проверяем прямые API вызовы
        logger.info("\n🔄 Прямые API вызовы...")

        import api_clients_main as api_clients
        from api_chunking import ChunkedAPIManager

        chunked_api = ChunkedAPIManager(api_clients)

        # WB Sales прямо
        try:
            wb_sales = await chunked_api.get_wb_sales_chunked(date_from, date_to)
            logger.info(f"WB Sales API: {len(wb_sales)} записей")
        except Exception as e:
            logger.error(f"WB Sales API ошибка: {e}")

        # Ozon прямо
        try:
            ozon_fbo = await chunked_api.get_ozon_fbo_chunked(date_from, date_to)
            logger.info(f"Ozon FBO API: {len(ozon_fbo or [])} записей")
        except Exception as e:
            logger.error(f"Ozon FBO API ошибка: {e}")

        try:
            ozon_fbs = await chunked_api.get_ozon_fbs_chunked(date_from, date_to)
            logger.info(f"Ozon FBS API: {len(ozon_fbs or [])} записей")
        except Exception as e:
            logger.error(f"Ozon FBS API ошибка: {e}")

        # Проверяем старый метод
        logger.info("\n📁 Старый метод WB...")
        try:
            wb_reports = await api_clients.download_wb_reports()
            if wb_reports and wb_reports.get("sales"):
                with open(wb_reports["sales"], encoding="utf-8") as f:
                    import json

                    old_sales = json.load(f)

                logger.info(f"Старый файл WB: {len(old_sales)} записей")

                # Фильтруем по датам
                filtered_sales = []
                for sale in old_sales:
                    sale_date = sale.get("date", "")[:10]
                    if date_from <= sale_date <= date_to:
                        filtered_sales.append(sale)

                logger.info(
                    f"Отфильтровано за {date_from}-{date_to}: {len(filtered_sales)} записей"
                )

                if filtered_sales:
                    logger.info("Пример записи:")
                    example = filtered_sales[0]
                    logger.info(f"  Дата: {example.get('date')}")
                    logger.info(f"  Реализация: {example.get('isRealization')}")
                    logger.info(f"  Цена: {example.get('priceWithDisc')} ₽")

        except Exception as e:
            logger.error(f"Ошибка старого метода: {e}")

        logger.info("\n✅ Диагностика короткого периода завершена")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_short_period())
