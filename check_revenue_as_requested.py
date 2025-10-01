#!/usr/bin/env python3
"""Проверка WB API за период 2025-08-16 → 2025-09-15
Ожидаемая выручка: ~72,105 ₽

И аналогично для Ozon - проверка данных за тот же период
Ожидаемая выручка: ~439,318 ₽

По примеру пользователя из задания.
"""

import asyncio
from datetime import date

from api_clients.ozon.sales_client import OzonSalesClient
from api_clients.wb.stats_client import WBStatsClient


async def check_wb_real_data():
    """Проверка WB API как в примере пользователя"""
    client = WBStatsClient()
    sales = await client.sales(date(2025, 8, 16), date(2025, 9, 15))

    total_revenue = 0
    for sale in sales:
        # WB API возвращает forPay как итоговую выручку
        total_revenue += sale.get("forPay", 0)

    print(f"WB реальная выручка: {total_revenue:.2f} ₽")
    print(f"Количество продаж: {len(sales)}")
    return total_revenue


async def check_ozon_real_data():
    """Проверка Ozon API аналогично WB"""
    client = OzonSalesClient()

    # Используем Analytics API для получения выручки
    analytics_data = await client.get_analytics_data(
        date(2025, 8, 16), date(2025, 9, 15), ["revenue"]
    )

    total_revenue = 0.0
    data_rows = analytics_data.get("result", {}).get("data", [])

    for row in data_rows:
        metrics = row.get("metrics", [])
        if metrics:
            revenue = float(metrics[0] or 0)
            total_revenue += revenue

    print(f"Ozon реальная выручка: {total_revenue:.2f} ₽")
    print(f"Количество записей: {len(data_rows)}")
    return total_revenue


async def main():
    """Основная функция проверки"""
    print("🔍 Проверяем WB и Ozon API за период 2025-08-16 → 2025-09-15")
    print("=" * 60)

    print("\n📊 WB API ПРОВЕРКА:")
    print("-" * 30)
    try:
        wb_revenue = await check_wb_real_data()
        expected_wb = 72105.0

        print(f"Ожидаемо: {expected_wb:.2f} ₽")
        print(f"Разница: {wb_revenue - expected_wb:+.2f} ₽")

        if abs(wb_revenue - expected_wb) <= expected_wb * 0.05:  # 5% допуск
            print("✅ WB: Результат соответствует ожиданиям!")
        else:
            print("⚠️  WB: Результат отличается от ожидаемого")

    except Exception as e:
        print(f"❌ Ошибка WB API: {e}")
        wb_revenue = 0

    print("\n📊 OZON API ПРОВЕРКА:")
    print("-" * 30)
    try:
        ozon_revenue = await check_ozon_real_data()
        expected_ozon = 439318.0

        print(f"Ожидаемо: {expected_ozon:.2f} ₽")
        print(f"Разница: {ozon_revenue - expected_ozon:+.2f} ₽")

        if abs(ozon_revenue - expected_ozon) <= expected_ozon * 0.05:  # 5% допуск
            print("✅ Ozon: Результат соответствует ожиданиям!")
        else:
            print("⚠️  Ozon: Результат отличается от ожидаемого")
            if ozon_revenue > expected_ozon:
                print("💡 Ozon показывает выручку выше ожидаемой - возможен рост продаж!")

    except Exception as e:
        print(f"❌ Ошибка Ozon API: {e}")
        ozon_revenue = 0

    print("\n📈 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    print("=" * 60)
    print(f"WB итоговая выручка:   {wb_revenue:>12,.2f} ₽")
    print(f"Ozon итоговая выручка: {ozon_revenue:>12,.2f} ₽")
    print(f"{'─' * 40}")
    print(f"Общая выручка:         {wb_revenue + ozon_revenue:>12,.2f} ₽")

    expected_total = 72105.0 + 439318.0
    actual_total = wb_revenue + ozon_revenue

    print(f"\nОжидалось всего:       {expected_total:>12,.2f} ₽")
    print(f"Получили всего:        {actual_total:>12,.2f} ₽")
    print(f"Разница:               {actual_total - expected_total:>+12,.2f} ₽")


if __name__ == "__main__":
    asyncio.run(main())
