#!/usr/bin/env python3
"""АНАЛИЗ ДАННЫХ ЗА АПРЕЛЬ-СЕНТЯБРЬ 2025
Сравнение системных данных с реальными показателями WB
"""

import asyncio
import logging

import api_clients_main as api_clients
from api_chunking import ChunkedAPIManager
from real_data_reports import RealDataFinancialReports

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def analyze_april_september_data():
    """Детальный анализ данных за апрель-сентябрь 2025"""
    logger.info("🔍 АНАЛИЗ ДАННЫХ ЗА АПРЕЛЬ-СЕНТЯБРЬ 2025")
    logger.info("=" * 60)

    # Реальные данные от пользователя
    REAL_DELIVERED = 413586  # ₽ выкупы
    REAL_ORDERS = 723738  # ₽ заказы

    logger.info("📊 РЕАЛЬНЫЕ ДАННЫЕ WB ЗА АПРЕЛЬ-СЕНТЯБРЬ:")
    logger.info(f"   Выкупы: {REAL_DELIVERED:,} ₽")
    logger.info(f"   Заказы: {REAL_ORDERS:,} ₽")
    logger.info("")

    reports = RealDataFinancialReports()
    chunked_api = ChunkedAPIManager(api_clients)

    # Получаем данные за весь период апрель-сентябрь
    date_from = "2025-04-01"
    date_to = "2025-09-30"

    logger.info(f"🔍 АНАЛИЗИРУЕМ ПЕРИОД: {date_from} → {date_to}")
    logger.info("")

    try:
        # Получаем сырые данные без обработки
        logger.info("📥 ПОЛУЧЕНИЕ СЫРЫХ ДАННЫХ:")
        sales_data = await chunked_api.get_wb_sales_chunked(date_from, date_to)
        orders_data = await chunked_api.get_wb_orders_chunked(date_from, date_to)

        logger.info(f"   Sales записей: {len(sales_data) if sales_data else 0}")
        logger.info(f"   Orders записей: {len(orders_data) if orders_data else 0}")
        logger.info("")

        if not sales_data:
            logger.error("❌ Нет Sales данных для анализа")
            return

        # Анализируем период покрытия данных
        logger.info("📅 АНАЛИЗ ПОКРЫТИЯ ДАННЫХ:")
        all_sales_dates = []
        for record in sales_data:
            raw_date = record.get("date", "")
            if "T" in raw_date:
                parsed_date = raw_date.split("T")[0]
            else:
                parsed_date = raw_date[:10]
            if parsed_date:
                all_sales_dates.append(parsed_date)

        if all_sales_dates:
            min_date = min(all_sales_dates)
            max_date = max(all_sales_dates)
            logger.info(f"   Диапазон Sales данных: {min_date} → {max_date}")

            # Проверяем попадание в наш период
            in_period = sum(1 for d in all_sales_dates if date_from <= d <= date_to)
            out_period = len(all_sales_dates) - in_period
            logger.info(f"   В периоде {date_from}-{date_to}: {in_period} записей")
            logger.info(f"   Вне периода: {out_period} записей")
        logger.info("")

        # Детальный анализ Sales данных
        logger.info("💰 АНАЛИЗ SALES ДАННЫХ (ВЫКУПЫ):")

        total_sales_price_with_disc = 0
        total_sales_for_pay = 0
        delivered_count = 0

        # Группировка по месяцам
        monthly_sales = {}

        for record in sales_data:
            # Фильтруем по периоду
            raw_date = record.get("date", "")
            if "T" in raw_date:
                parsed_date = raw_date.split("T")[0]
            else:
                parsed_date = raw_date[:10]

            if not (date_from <= parsed_date <= date_to):
                continue

            is_realization = record.get("isRealization", False)
            if not is_realization:
                continue

            price_with_disc = record.get("priceWithDisc", 0) or 0
            for_pay = record.get("forPay", 0) or 0

            total_sales_price_with_disc += price_with_disc
            total_sales_for_pay += for_pay
            delivered_count += 1

            # Группировка по месяцам
            month_key = parsed_date[:7]  # YYYY-MM
            if month_key not in monthly_sales:
                monthly_sales[month_key] = {"count": 0, "price_with_disc": 0, "for_pay": 0}

            monthly_sales[month_key]["count"] += 1
            monthly_sales[month_key]["price_with_disc"] += price_with_disc
            monthly_sales[month_key]["for_pay"] += for_pay

        logger.info(f"   Всего продаж (priceWithDisc): {total_sales_price_with_disc:,.0f} ₽")
        logger.info(f"   К перечислению (forPay): {total_sales_for_pay:,.0f} ₽")
        logger.info(f"   Количество выкупов: {delivered_count}")
        logger.info("")

        # Помесячная разбивка
        logger.info("📈 ПОМЕСЯЧНАЯ РАЗБИВКА SALES:")
        for month in sorted(monthly_sales.keys()):
            data = monthly_sales[month]
            logger.info(
                f"   {month}: {data['count']} шт, {data['price_with_disc']:,.0f} ₽ (priceWithDisc)"
            )

        logger.info("")

        # Анализ Orders данных
        logger.info("🛒 АНАЛИЗ ORDERS ДАННЫХ (ЗАКАЗЫ):")

        total_orders_price_with_disc = 0
        total_orders_total_price = 0
        orders_count = 0

        monthly_orders = {}

        for record in orders_data:
            # Фильтруем по периоду
            raw_date = record.get("date", "")
            if "T" in raw_date:
                parsed_date = raw_date.split("T")[0]
            else:
                parsed_date = raw_date[:10]

            if not (date_from <= parsed_date <= date_to):
                continue

            price_with_disc = record.get("priceWithDisc", 0) or 0
            total_price = record.get("totalPrice", 0) or 0

            total_orders_price_with_disc += price_with_disc
            total_orders_total_price += total_price
            orders_count += 1

            # Группировка по месяцам
            month_key = parsed_date[:7]
            if month_key not in monthly_orders:
                monthly_orders[month_key] = {"count": 0, "price_with_disc": 0, "total_price": 0}

            monthly_orders[month_key]["count"] += 1
            monthly_orders[month_key]["price_with_disc"] += price_with_disc
            monthly_orders[month_key]["total_price"] += total_price

        logger.info(f"   Всего заказов (priceWithDisc): {total_orders_price_with_disc:,.0f} ₽")
        logger.info(f"   Всего заказов (totalPrice): {total_orders_total_price:,.0f} ₽")
        logger.info(f"   Количество заказов: {orders_count}")
        logger.info("")

        # Помесячная разбивка заказов
        logger.info("📈 ПОМЕСЯЧНАЯ РАЗБИВКА ORDERS:")
        for month in sorted(monthly_orders.keys()):
            data = monthly_orders[month]
            logger.info(
                f"   {month}: {data['count']} шт, {data['price_with_disc']:,.0f} ₽ (priceWithDisc)"
            )

        logger.info("")

        # СРАВНЕНИЕ С РЕАЛЬНЫМИ ДАННЫМИ
        logger.info("🎯 СРАВНЕНИЕ С РЕАЛЬНЫМИ ДАННЫМИ:")
        logger.info("")

        # Выкупы
        sales_ratio = total_sales_price_with_disc / REAL_DELIVERED if REAL_DELIVERED > 0 else 0
        sales_diff = total_sales_price_with_disc - REAL_DELIVERED

        logger.info("ВЫКУПЫ:")
        logger.info(f"   Система (priceWithDisc): {total_sales_price_with_disc:,.0f} ₽")
        logger.info(f"   Реальные данные WB: {REAL_DELIVERED:,.0f} ₽")
        logger.info(f"   Соотношение: {sales_ratio:.2f}x")
        logger.info(f"   Разница: {sales_diff:,.0f} ₽")

        if abs(sales_ratio - 1.0) < 0.1:
            logger.info("   ✅ СООТВЕТСТВУЕТ (±10%)")
        elif sales_ratio > 1.2:
            logger.info(f"   ❌ ЗАВЫШЕНИЕ на {((sales_ratio - 1) * 100):.0f}%")
        else:
            logger.info(f"   ⚠️  ЗАНИЖЕНИЕ на {((1 - sales_ratio) * 100):.0f}%")

        logger.info("")

        # Заказы
        orders_ratio = total_orders_price_with_disc / REAL_ORDERS if REAL_ORDERS > 0 else 0
        orders_diff = total_orders_price_with_disc - REAL_ORDERS

        logger.info("ЗАКАЗЫ:")
        logger.info(f"   Система (priceWithDisc): {total_orders_price_with_disc:,.0f} ₽")
        logger.info(f"   Реальные данные WB: {REAL_ORDERS:,.0f} ₽")
        logger.info(f"   Соотношение: {orders_ratio:.2f}x")
        logger.info(f"   Разница: {orders_diff:,.0f} ₽")

        if abs(orders_ratio - 1.0) < 0.1:
            logger.info("   ✅ СООТВЕТСТВУЕТ (±10%)")
        elif orders_ratio > 1.2:
            logger.info(f"   ❌ ЗАВЫШЕНИЕ на {((orders_ratio - 1) * 100):.0f}%")
        else:
            logger.info(f"   ⚠️  ЗАНИЖЕНИЕ на {((1 - orders_ratio) * 100):.0f}%")

        logger.info("")

        # ДИАГНОСТИКА ВОЗМОЖНЫХ ПРИЧИН
        logger.info("🔍 ДИАГНОСТИКА ВОЗМОЖНЫХ ПРИЧИН РАСХОЖДЕНИЯ:")

        if sales_ratio > 1.1 or orders_ratio > 1.1:
            logger.warning("❌ ОБНАРУЖЕНО ЗАВЫШЕНИЕ - возможные причины:")
            logger.warning("   1. Дублирование записей в API")
            logger.warning("   2. Включение возвратов как продаж")
            logger.warning("   3. Неправильная обработка поля isRealization")
            logger.warning("   4. Различие в методологии подсчета WB")

            # Проверяем дубликаты
            logger.info("")
            logger.info("🔍 ПРОВЕРКА ДУБЛИКАТОВ:")

            sale_ids = []
            for record in sales_data:
                raw_date = record.get("date", "")
                if "T" in raw_date:
                    parsed_date = raw_date.split("T")[0]
                else:
                    parsed_date = raw_date[:10]

                if date_from <= parsed_date <= date_to:
                    sale_id = record.get("saleID", "")
                    if sale_id:
                        sale_ids.append(sale_id)

            unique_sale_ids = set(sale_ids)
            duplicates_count = len(sale_ids) - len(unique_sale_ids)

            logger.info(f"   Всего saleID: {len(sale_ids)}")
            logger.info(f"   Уникальных saleID: {len(unique_sale_ids)}")
            logger.info(f"   Дубликатов: {duplicates_count}")

            if duplicates_count > 0:
                logger.warning("   ⚠️  НАЙДЕНЫ ДУБЛИКАТЫ! Это может объяснять завышение")
            else:
                logger.info("   ✅ Дубликатов не найдено")

        return {
            "system_sales": total_sales_price_with_disc,
            "system_orders": total_orders_price_with_disc,
            "real_sales": REAL_DELIVERED,
            "real_orders": REAL_ORDERS,
            "sales_ratio": sales_ratio,
            "orders_ratio": orders_ratio,
            "delivered_count": delivered_count,
            "orders_count": orders_count,
            "duplicates_found": duplicates_count if "duplicates_count" in locals() else 0,
        }

    except Exception as e:
        logger.error(f"❌ Ошибка анализа: {e}")
        return None


if __name__ == "__main__":
    result = asyncio.run(analyze_april_september_data())
