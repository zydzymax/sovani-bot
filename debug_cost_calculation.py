#!/usr/bin/env python3
"""Отладка расчета себестоимости"""

import asyncio
import json


async def debug_cost_calculation():
    """Отладка расчета себестоимости"""
    print("🔍 ОТЛАДКА РАСЧЕТА СЕБЕСТОИМОСТИ")
    print("=" * 50)

    # 1. Загружаем данные о продажах
    print("📊 Данные продаж WB:")
    with open("reports/wb_sales_20250920.json", encoding="utf-8") as f:
        wb_sales = json.load(f)

    # Группируем продажи по артикулам
    sales_by_sku = {}
    total_sold_units = 0

    for sale in wb_sales:
        if sale.get("isRealization"):  # Только реализованные
            sku = sale.get("supplierArticle", "Unknown")
            price = sale.get("priceWithDisc", 0)

            if sku not in sales_by_sku:
                sales_by_sku[sku] = {"count": 0, "revenue": 0}

            sales_by_sku[sku]["count"] += 1
            sales_by_sku[sku]["revenue"] += price
            total_sold_units += 1

    print(f"  Всего продано единиц WB: {total_sold_units}")
    print("\n  Топ-5 проданных товаров WB:")
    top_wb = sorted(sales_by_sku.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
    for sku, data in top_wb:
        print(f"    {sku}: {data['count']} шт, {data['revenue']:.0f} ₽")

    # 2. Загружаем данные о продажах Ozon
    print("\n📊 Данные продаж Ozon:")
    from datetime import datetime

    from api_clients.ozon.sales_client import OzonSalesClient

    sales_client = OzonSalesClient()
    date_from = datetime.strptime("2025-09-13", "%Y-%m-%d").date()
    date_to = datetime.strptime("2025-09-20", "%Y-%m-%d").date()

    ozon_transactions = await sales_client.get_transactions(date_from, date_to)

    ozon_sales_by_sku = {}
    ozon_sold_units = 0

    for transaction in ozon_transactions:
        if transaction.get("operation_type") == "OperationDeliveryCharge":
            sku = transaction.get("posting", {}).get("sku")
            amount = abs(float(transaction.get("amount", 0)))

            if sku and sku not in ozon_sales_by_sku:
                ozon_sales_by_sku[sku] = {"count": 0, "revenue": 0}

            if sku:
                ozon_sales_by_sku[sku]["count"] += 1
                ozon_sales_by_sku[sku]["revenue"] += amount
                ozon_sold_units += 1

    print(f"  Всего продано единиц Ozon: {ozon_sold_units}")
    print("\n  Топ-5 проданных товаров Ozon:")
    top_ozon = sorted(ozon_sales_by_sku.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
    for sku, data in top_ozon:
        print(f"    {sku}: {data['count']} шт, {data['revenue']:.0f} ₽")

    # 3. Загружаем шаблон себестоимости
    print("\n💰 Анализ себестоимости:")
    with open("cost_data/cost_data_20250920_010807.json", encoding="utf-8") as f:
        cost_data = json.load(f)

    sku_costs = cost_data.get("sku_costs", {})

    # 4. Проверяем соответствие
    print("\n🔍 Соответствие продаж и себестоимости:")
    total_calculated_cost = 0
    matched_units = 0
    unmatched_skus = []

    # WB товары
    print("\n  WB товары:")
    for sku, sale_data in sales_by_sku.items():
        wb_key = f"WB_{sku}"
        if wb_key in sku_costs:
            cost_per_unit = sku_costs[wb_key]["cost_per_unit"]
            total_cost = cost_per_unit * sale_data["count"]
            total_calculated_cost += total_cost
            matched_units += sale_data["count"]
            print(f"    ✅ {sku}: {sale_data['count']} шт × {cost_per_unit} ₽ = {total_cost:.0f} ₽")
        else:
            unmatched_skus.append(f"WB_{sku}")
            print(f"    ❌ {sku}: {sale_data['count']} шт - НЕТ в шаблоне!")

    # Ozon товары
    print("\n  Ozon товары:")
    for sku, sale_data in ozon_sales_by_sku.items():
        if not sku:
            continue

        ozon_key = f"Ozon_{sku}"
        if ozon_key in sku_costs:
            cost_per_unit = sku_costs[ozon_key]["cost_per_unit"]
            total_cost = cost_per_unit * sale_data["count"]
            total_calculated_cost += total_cost
            matched_units += sale_data["count"]
            print(f"    ✅ {sku}: {sale_data['count']} шт × {cost_per_unit} ₽ = {total_cost:.0f} ₽")
        else:
            unmatched_skus.append(f"Ozon_{sku}")
            print(f"    ❌ {sku}: {sale_data['count']} шт - НЕТ в шаблоне!")

    # 5. Итоги
    print("\n📋 ИТОГИ:")
    print(f"  Всего продано единиц: {total_sold_units + ozon_sold_units}")
    print(f"  Найдено в шаблоне: {matched_units} единиц")
    print(f"  Не найдено: {total_sold_units + ozon_sold_units - matched_units} единиц")
    print(f"  Рассчитанная себестоимость: {total_calculated_cost:.2f} ₽")
    print(
        f"  Средняя себестоимость за единицу: {total_calculated_cost/matched_units:.2f} ₽"
        if matched_units > 0
        else "  Нет данных"
    )

    if unmatched_skus:
        print(f"\n❌ Товары БЕЗ себестоимости ({len(unmatched_skus)}):")
        for sku in unmatched_skus[:10]:  # Показываем первые 10
            print(f"    {sku}")
        if len(unmatched_skus) > 10:
            print(f"    ... и еще {len(unmatched_skus) - 10}")

    return total_calculated_cost, matched_units


if __name__ == "__main__":
    cost, units = asyncio.run(debug_cost_calculation())
    print(
        f"\n🎯 ПРОБЛЕМА: На {units} единиц себестоимость {cost:.0f} ₽ = {cost/units:.0f} ₽/шт"
        if units > 0
        else "\n❌ Нет соответствий!"
    )
