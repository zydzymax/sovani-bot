#!/usr/bin/env python3
"""Аналитика оборачиваемости товаров по складам
Для отслеживания и рекомендаций поставок
"""

import glob
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class WarehouseTurnoverAnalytics:
    """Аналитика оборачиваемости товаров по складам"""

    async def get_detailed_warehouse_stocks(self) -> dict[str, Any]:
        """Получение детальных остатков с разбивкой по складам"""
        try:
            wb_warehouse_data = await self._get_wb_warehouse_details()
            ozon_warehouse_data = await self._get_ozon_warehouse_details()

            return {
                "wb": wb_warehouse_data,
                "ozon": ozon_warehouse_data,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Ошибка получения детальных остатков: {e}")
            return {}

    async def _get_wb_warehouse_details(self) -> dict[str, Any]:
        """Детальная структура остатков WB по складам"""
        try:
            # Ищем файл остатков WB
            pattern = "reports/wb_stock_*.json"
            files = glob.glob(pattern)

            if not files:
                return {}

            latest_file = max(files)
            with open(latest_file, encoding="utf-8") as f:
                data = json.load(f)

            warehouse_details = {}

            for item in data:
                barcode = item.get("barcode", "")
                warehouse = item.get("warehouseName", "")
                article = item.get("supplierArticle", "")
                size = item.get("techSize", "")
                quantity = item.get("quantity", 0)

                if not barcode:
                    continue

                # Создаем уникальный ключ для SKU
                sku_key = f"{article}_{size}"

                if sku_key not in warehouse_details:
                    warehouse_details[sku_key] = {
                        "barcode": barcode,
                        "article": article,
                        "size": size,
                        "subject": item.get("subject", ""),
                        "category": item.get("category", ""),
                        "brand": item.get("brand", ""),
                        "warehouses": {},
                        "total_quantity": 0,
                    }

                warehouse_details[sku_key]["warehouses"][warehouse] = quantity
                warehouse_details[sku_key]["total_quantity"] += quantity

            return {
                "total_skus": len(warehouse_details),
                "total_warehouses": len(
                    set(w for sku in warehouse_details.values() for w in sku["warehouses"].keys())
                ),
                "skus": warehouse_details,
            }

        except Exception as e:
            logger.error(f"Ошибка получения WB складских данных: {e}")
            return {}

    async def _get_ozon_warehouse_details(self) -> dict[str, Any]:
        """Детальная структура остатков Ozon"""
        try:
            # Ищем файл остатков Ozon
            pattern = "reports/ozon_stocks_*.json"
            files = glob.glob(pattern)

            if not files:
                return {}

            latest_file = max(files)
            with open(latest_file, encoding="utf-8") as f:
                data = json.load(f)

            warehouse_details = {}

            for item in data:
                product_id = item.get("product_id")
                offer_id = item.get("offer_id", "")
                stock = item.get("stock", 0)
                fbo_stock = item.get("fbo_stock", 0)
                fbs_stock = item.get("fbs_stock", 0)
                reserved = item.get("reserved", 0)

                if not product_id:
                    continue

                # Группируем по product_id (уникальный товар)
                if product_id not in warehouse_details:
                    warehouse_details[product_id] = {
                        "product_id": product_id,
                        "offer_id": offer_id,
                        "total_stock": 0,
                        "fbo_stock": 0,
                        "fbs_stock": 0,
                        "reserved": 0,
                        "status": "unknown",
                    }

                # Суммируем остатки (может быть несколько записей для одного product_id)
                warehouse_details[product_id]["total_stock"] += stock
                warehouse_details[product_id]["fbo_stock"] += fbo_stock
                warehouse_details[product_id]["fbs_stock"] += fbs_stock
                warehouse_details[product_id]["reserved"] += reserved

            # Определяем статусы товаров
            on_warehouse = 0
            in_transit = 0
            zero_stock = 0

            for product_id, data in warehouse_details.items():
                if data["total_stock"] > 0:
                    data["status"] = "on_warehouse"
                    on_warehouse += 1
                elif data["reserved"] > 0:
                    data["status"] = "in_transit"
                    in_transit += 1
                else:
                    data["status"] = "zero_stock"
                    zero_stock += 1

            return {
                "total_products": len(warehouse_details),
                "on_warehouse": on_warehouse,
                "in_transit": in_transit,
                "zero_stock": zero_stock,
                "products": warehouse_details,
            }

        except Exception as e:
            logger.error(f"Ошибка получения Ozon складских данных: {e}")
            return {}

    async def calculate_sku_turnover(self, sku_barcode: str, days: int = 30) -> dict[str, Any]:
        """Расчет оборачиваемости конкретного SKU за период"""
        try:
            # TODO: Получить данные о продажах за последние 30 дней
            # Здесь будет интеграция с sales data

            return {
                "sku_barcode": sku_barcode,
                "period_days": days,
                "total_sold": 0,  # Будет рассчитано из данных продаж
                "daily_average": 0,
                "current_stock": 0,  # Из складских остатков
                "days_of_supply": 0,  # Дней до окончания запаса
                "recommended_restock": False,
                "recommended_quantity": 0,
            }

        except Exception as e:
            logger.error(f"Ошибка расчета оборачиваемости для {sku_barcode}: {e}")
            return {}

    async def get_restock_recommendations(self) -> list[dict[str, Any]]:
        """Рекомендации по пополнению товаров на складах"""
        try:
            warehouse_data = await self.get_detailed_warehouse_stocks()
            recommendations = []

            # Для WB - анализируем по складам
            if "wb" in warehouse_data:
                wb_data = warehouse_data["wb"]
                for sku_key, sku_data in wb_data.get("skus", {}).items():
                    # TODO: Добавить логику рекомендаций на основе:
                    # - Текущих остатков
                    # - Истории продаж
                    # - Сезонности
                    pass

            # Для Ozon - анализируем статусы товаров
            if "ozon" in warehouse_data:
                ozon_data = warehouse_data["ozon"]
                for product_id, product_data in ozon_data.get("products", {}).items():
                    if product_data["status"] == "zero_stock":
                        recommendations.append(
                            {
                                "platform": "Ozon",
                                "product_id": product_id,
                                "offer_id": product_data["offer_id"],
                                "issue": "Нулевые остатки",
                                "priority": "high",
                            }
                        )
                    elif product_data["status"] == "in_transit":
                        recommendations.append(
                            {
                                "platform": "Ozon",
                                "product_id": product_id,
                                "offer_id": product_data["offer_id"],
                                "issue": f"В пути: {product_data['reserved']} ед.",
                                "priority": "medium",
                            }
                        )

            return recommendations

        except Exception as e:
            logger.error(f"Ошибка генерации рекомендаций: {e}")
            return []


# Инициализация
warehouse_analytics = WarehouseTurnoverAnalytics()

if __name__ == "__main__":
    import asyncio

    async def test():
        analytics = WarehouseTurnoverAnalytics()

        print("=== ДЕТАЛЬНЫЕ ОСТАТКИ ПО СКЛАДАМ ===")
        data = await analytics.get_detailed_warehouse_stocks()

        if "wb" in data:
            wb_data = data["wb"]
            print(f"WB: {wb_data['total_skus']} SKU на {wb_data['total_warehouses']} складах")

        if "ozon" in data:
            ozon_data = data["ozon"]
            print(f"Ozon: {ozon_data['total_products']} товаров")
            print(f"  - На складе: {ozon_data['on_warehouse']}")
            print(f"  - В пути: {ozon_data['in_transit']}")
            print(f"  - Нулевые остатки: {ozon_data['zero_stock']}")

        print("\n=== РЕКОМЕНДАЦИИ ===")
        recommendations = await analytics.get_restock_recommendations()
        for rec in recommendations[:5]:
            print(f"- {rec['platform']}: {rec['offer_id']} - {rec['issue']}")

    asyncio.run(test())
