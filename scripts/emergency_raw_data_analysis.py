#!/usr/bin/env python3
"""ЭКСТРЕННЫЙ АНАЛИЗ СЫРЫХ ДАННЫХ API
Получение сырых данных от WB API для выявления причин завышения в 10 раз
"""

import asyncio
import json
import logging
from datetime import datetime

import api_clients_main as api_clients
from api_chunking import ChunkedAPIManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmergencyRawDataAnalyzer:
    """Экстренный анализатор сырых данных API"""

    def __init__(self):
        self.chunked_manager = ChunkedAPIManager(api_clients)
        self.raw_sales_data = []
        self.raw_orders_data = []

    async def get_raw_api_data(self, date_from: str, date_to: str):
        """Получение сырых данных от API без обработки"""
        logger.info("🚨 ЭКСТРЕННЫЙ АНАЛИЗ СЫРЫХ ДАННЫХ API")
        logger.info("=" * 60)
        logger.info(f"📅 Период: {date_from} - {date_to}")

        try:
            # Получаем сырые данные Sales API
            logger.info("\n🔍 ПОЛУЧЕНИЕ СЫРЫХ SALES ДАННЫХ:")
            self.raw_sales_data = await self.chunked_manager.get_wb_sales_chunked(
                date_from, date_to
            )

            sales_count = len(self.raw_sales_data) if self.raw_sales_data else 0
            logger.info(f"   📊 Получено Sales записей: {sales_count}")

            # Получаем сырые данные Orders API
            logger.info("\n🔍 ПОЛУЧЕНИЕ СЫРЫХ ORDERS ДАННЫХ:")
            self.raw_orders_data = await self.chunked_manager.get_wb_orders_chunked(
                date_from, date_to
            )

            orders_count = len(self.raw_orders_data) if self.raw_orders_data else 0
            logger.info(f"   📊 Получено Orders записей: {orders_count}")

            return {"sales_count": sales_count, "orders_count": orders_count, "success": True}

        except Exception as e:
            logger.error(f"❌ Ошибка получения сырых данных: {e}")
            return {"success": False, "error": str(e)}

    def analyze_price_format(self):
        """Анализ формата цен в сырых данных"""
        logger.info("\n💰 АНАЛИЗ ФОРМАТА ЦЕН:")
        logger.info("=" * 40)

        # Анализ Sales данных
        if self.raw_sales_data and len(self.raw_sales_data) > 0:
            logger.info("📊 АНАЛИЗ ЦЕН В SALES:")

            sample_size = min(10, len(self.raw_sales_data))
            price_stats = {"forPay": [], "priceWithDisc": [], "totalPrice": []}

            for i, sale in enumerate(self.raw_sales_data[:sample_size]):
                forPay = sale.get("forPay", 0)
                priceWithDisc = sale.get("priceWithDisc", 0)
                totalPrice = sale.get("totalPrice", 0)

                price_stats["forPay"].append(forPay)
                price_stats["priceWithDisc"].append(priceWithDisc)
                price_stats["totalPrice"].append(totalPrice)

                logger.info(f"   Продажа {i+1}:")
                logger.info(f"      forPay: {forPay}")
                logger.info(f"      priceWithDisc: {priceWithDisc}")
                logger.info(f"      totalPrice: {totalPrice}")
                logger.info(
                    f"      Соотношение priceWithDisc/forPay: {priceWithDisc/forPay if forPay > 0 else 'N/A':.2f}"
                )

            # Статистика по ценам
            logger.info(f"\n📈 СТАТИСТИКА ЦЕН (первые {sample_size} записей):")
            for field, values in price_stats.items():
                if values:
                    avg_val = sum(values) / len(values)
                    min_val = min(values)
                    max_val = max(values)
                    logger.info(f"   {field}:")
                    logger.info(f"      Среднее: {avg_val:.2f}")
                    logger.info(f"      Мин: {min_val:.2f}")
                    logger.info(f"      Макс: {max_val:.2f}")

        # Анализ Orders данных
        if self.raw_orders_data and len(self.raw_orders_data) > 0:
            logger.info("\n📊 АНАЛИЗ ЦЕН В ORDERS:")

            sample_size = min(10, len(self.raw_orders_data))

            for i, order in enumerate(self.raw_orders_data[:sample_size]):
                priceWithDisc = order.get("priceWithDisc", 0)
                totalPrice = order.get("totalPrice", 0)

                logger.info(f"   Заказ {i+1}:")
                logger.info(f"      priceWithDisc: {priceWithDisc}")
                logger.info(f"      totalPrice: {totalPrice}")
                logger.info(
                    f"      Соотношение totalPrice/priceWithDisc: {totalPrice/priceWithDisc if priceWithDisc > 0 else 'N/A':.2f}"
                )

        return price_stats

    def detect_duplicates(self):
        """Обнаружение дубликатов в данных"""
        logger.info("\n🔍 ОБНАРУЖЕНИЕ ДУБЛИКАТОВ:")
        logger.info("=" * 40)

        duplicates_analysis = {
            "sales_duplicates": 0,
            "orders_duplicates": 0,
            "sales_unique_ids": set(),
            "orders_unique_ids": set(),
        }

        # Анализ дубликатов в Sales
        if self.raw_sales_data:
            logger.info("📊 АНАЛИЗ ДУБЛИКАТОВ В SALES:")

            sale_ids = []
            for sale in self.raw_sales_data:
                sale_id = sale.get("saleID")
                if sale_id:
                    sale_ids.append(sale_id)
                    duplicates_analysis["sales_unique_ids"].add(sale_id)

            total_sales = len(sale_ids)
            unique_sales = len(duplicates_analysis["sales_unique_ids"])
            duplicates_analysis["sales_duplicates"] = total_sales - unique_sales

            logger.info(f"   Всего записей: {total_sales}")
            logger.info(f"   Уникальных ID: {unique_sales}")
            logger.info(f"   Дубликатов: {duplicates_analysis['sales_duplicates']}")

            if duplicates_analysis["sales_duplicates"] > 0:
                logger.info(
                    f"   ⚠️ НАЙДЕНЫ ДУБЛИКАТЫ В SALES: {duplicates_analysis['sales_duplicates']}"
                )

                # Показываем примеры дубликатов
                from collections import Counter

                id_counts = Counter(sale_ids)
                duplicated_ids = {k: v for k, v in id_counts.items() if v > 1}

                logger.info("   Примеры дублированных ID:")
                for dup_id, count in list(duplicated_ids.items())[:5]:
                    logger.info(f"      {dup_id}: {count} раз")

        # Анализ дубликатов в Orders
        if self.raw_orders_data:
            logger.info("\n📊 АНАЛИЗ ДУБЛИКАТОВ В ORDERS:")

            order_ids = []
            for order in self.raw_orders_data:
                order_id = (
                    order.get("odid")
                    or order.get("orderID")
                    or f"order_{order.get('date', 'unknown')}"
                )
                order_ids.append(order_id)
                duplicates_analysis["orders_unique_ids"].add(order_id)

            total_orders = len(order_ids)
            unique_orders = len(duplicates_analysis["orders_unique_ids"])
            duplicates_analysis["orders_duplicates"] = total_orders - unique_orders

            logger.info(f"   Всего записей: {total_orders}")
            logger.info(f"   Уникальных ID: {unique_orders}")
            logger.info(f"   Дубликатов: {duplicates_analysis['orders_duplicates']}")

            if duplicates_analysis["orders_duplicates"] > 0:
                logger.info(
                    f"   ⚠️ НАЙДЕНЫ ДУБЛИКАТЫ В ORDERS: {duplicates_analysis['orders_duplicates']}"
                )

        return duplicates_analysis

    def calculate_real_aggregations(self):
        """Расчет реальных агрегаций с учетом найденных проблем"""
        logger.info("\n📊 РАСЧЕТ РЕАЛЬНЫХ АГРЕГАЦИЙ:")
        logger.info("=" * 40)

        real_calculations = {}

        # Sales расчеты
        if self.raw_sales_data:
            logger.info("💰 SALES РАСЧЕТЫ:")

            # Фильтруем только реализации
            realizations = [s for s in self.raw_sales_data if s.get("isRealization", True)]

            # Удаляем дубликаты по saleID
            unique_realizations = {}
            for sale in realizations:
                sale_id = sale.get("saleID")
                if sale_id and sale_id not in unique_realizations:
                    unique_realizations[sale_id] = sale

            unique_sales_list = list(unique_realizations.values())

            # Расчеты
            total_forPay = sum(s.get("forPay", 0) for s in unique_sales_list)
            total_priceWithDisc = sum(s.get("priceWithDisc", 0) for s in unique_sales_list)
            total_totalPrice = sum(s.get("totalPrice", 0) for s in unique_sales_list)

            real_calculations["sales"] = {
                "total_records": len(self.raw_sales_data),
                "realizations_count": len(realizations),
                "unique_realizations_count": len(unique_sales_list),
                "duplicates_removed": len(realizations) - len(unique_sales_list),
                "total_forPay": total_forPay,
                "total_priceWithDisc": total_priceWithDisc,
                "total_totalPrice": total_totalPrice,
            }

            logger.info(f"   Всего записей: {len(self.raw_sales_data)}")
            logger.info(f"   isRealization=true: {len(realizations)}")
            logger.info(f"   Уникальных после дедупликации: {len(unique_sales_list)}")
            logger.info(f"   Удалено дубликатов: {len(realizations) - len(unique_sales_list)}")
            logger.info(f"   Сумма forPay: {total_forPay:,.2f} ₽")
            logger.info(f"   Сумма priceWithDisc: {total_priceWithDisc:,.2f} ₽")
            logger.info(f"   Сумма totalPrice: {total_totalPrice:,.2f} ₽")

        # Orders расчеты
        if self.raw_orders_data:
            logger.info("\n💰 ORDERS РАСЧЕТЫ:")

            # Удаляем дубликаты по составному ключу
            unique_orders = {}
            for order in self.raw_orders_data:
                order_key = f"{order.get('date', '')}_{order.get('nmId', '')}_{order.get('priceWithDisc', 0)}"
                if order_key not in unique_orders:
                    unique_orders[order_key] = order

            unique_orders_list = list(unique_orders.values())

            # Расчеты
            total_priceWithDisc = sum(o.get("priceWithDisc", 0) for o in unique_orders_list)
            total_totalPrice = sum(o.get("totalPrice", 0) for o in unique_orders_list)

            real_calculations["orders"] = {
                "total_records": len(self.raw_orders_data),
                "unique_orders_count": len(unique_orders_list),
                "duplicates_removed": len(self.raw_orders_data) - len(unique_orders_list),
                "total_priceWithDisc": total_priceWithDisc,
                "total_totalPrice": total_totalPrice,
            }

            logger.info(f"   Всего записей: {len(self.raw_orders_data)}")
            logger.info(f"   Уникальных после дедупликации: {len(unique_orders_list)}")
            logger.info(
                f"   Удалено дубликатов: {len(self.raw_orders_data) - len(unique_orders_list)}"
            )
            logger.info(f"   Сумма priceWithDisc: {total_priceWithDisc:,.2f} ₽")
            logger.info(f"   Сумма totalPrice: {total_totalPrice:,.2f} ₽")

        return real_calculations

    def compare_with_expected(self, real_calculations):
        """Сравнение с ожидаемыми реальными данными"""
        logger.info("\n🎯 СРАВНЕНИЕ С РЕАЛЬНЫМИ ДАННЫМИ:")
        logger.info("=" * 40)

        # Реальные данные от пользователя
        expected_orders = 113595  # ₽
        expected_delivered = 60688  # ₽

        comparison = {}

        if "sales" in real_calculations:
            sales_data = real_calculations["sales"]

            logger.info("📊 СРАВНЕНИЕ ПРОДАЖ (ВЫКУПОВ):")
            logger.info(f"   Ожидаемые выкупы: {expected_delivered:,.0f} ₽")
            logger.info(f"   Система (forPay): {sales_data['total_forPay']:,.0f} ₽")
            logger.info(f"   Система (priceWithDisc): {sales_data['total_priceWithDisc']:,.0f} ₽")

            ratio_forPay = (
                sales_data["total_forPay"] / expected_delivered if expected_delivered > 0 else 0
            )
            ratio_priceWithDisc = (
                sales_data["total_priceWithDisc"] / expected_delivered
                if expected_delivered > 0
                else 0
            )

            logger.info(f"   Соотношение forPay/ожидаемые: {ratio_forPay:.2f}x")
            logger.info(f"   Соотношение priceWithDisc/ожидаемые: {ratio_priceWithDisc:.2f}x")

            comparison["sales"] = {
                "expected": expected_delivered,
                "forPay": sales_data["total_forPay"],
                "priceWithDisc": sales_data["total_priceWithDisc"],
                "ratio_forPay": ratio_forPay,
                "ratio_priceWithDisc": ratio_priceWithDisc,
            }

        if "orders" in real_calculations:
            orders_data = real_calculations["orders"]

            logger.info("\n📊 СРАВНЕНИЕ ЗАКАЗОВ:")
            logger.info(f"   Ожидаемые заказы: {expected_orders:,.0f} ₽")
            logger.info(f"   Система (priceWithDisc): {orders_data['total_priceWithDisc']:,.0f} ₽")

            ratio_orders = (
                orders_data["total_priceWithDisc"] / expected_orders if expected_orders > 0 else 0
            )

            logger.info(f"   Соотношение система/ожидаемые: {ratio_orders:.2f}x")

            comparison["orders"] = {
                "expected": expected_orders,
                "system": orders_data["total_priceWithDisc"],
                "ratio": ratio_orders,
            }

        return comparison

    def save_raw_analysis_report(self, real_calculations, comparison, duplicates_analysis):
        """Сохранение детального отчета"""
        report = {
            "analysis_date": datetime.now().isoformat(),
            "analysis_type": "emergency_raw_data_analysis",
            "period": "2025-01-01 to 2025-01-31",
            "raw_data_counts": {
                "sales_records": len(self.raw_sales_data) if self.raw_sales_data else 0,
                "orders_records": len(self.raw_orders_data) if self.raw_orders_data else 0,
            },
            "duplicates_analysis": duplicates_analysis,
            "real_calculations": real_calculations,
            "comparison_with_expected": comparison,
            "conclusions": {
                "primary_issue": "API данные содержат дубликаты и завышенные суммы",
                "duplication_impact": "Дубликаты увеличивают суммы",
                "price_format_issue": "Возможны проблемы с форматом цен",
                "correction_needed": "Требуется дедупликация и корректировка",
            },
        }

        filename = f"emergency_raw_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"/root/sovani_bot/reports/{filename}"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"\n💾 Отчет сохранен: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            return None


async def main():
    """Основная функция экстренного анализа"""
    analyzer = EmergencyRawDataAnalyzer()

    # Период анализа - январь 2025
    date_from = "2025-01-01"
    date_to = "2025-01-31"

    logger.info("🚨 ЗАПУСК ЭКСТРЕННОГО АНАЛИЗА СЫРЫХ ДАННЫХ")

    # Получаем сырые данные
    raw_data_result = await analyzer.get_raw_api_data(date_from, date_to)

    if raw_data_result["success"]:
        # Анализируем формат цен
        price_stats = analyzer.analyze_price_format()

        # Обнаруживаем дубликаты
        duplicates_analysis = analyzer.detect_duplicates()

        # Рассчитываем реальные агрегации
        real_calculations = analyzer.calculate_real_aggregations()

        # Сравниваем с ожидаемыми данными
        comparison = analyzer.compare_with_expected(real_calculations)

        # Сохраняем отчет
        report_path = analyzer.save_raw_analysis_report(
            real_calculations, comparison, duplicates_analysis
        )

        logger.info("\n🎉 ЭКСТРЕННЫЙ АНАЛИЗ ЗАВЕРШЕН!")
        logger.info(f"📄 Отчет: {report_path}")

        return real_calculations, comparison, duplicates_analysis
    else:
        logger.error("❌ Не удалось получить сырые данные")
        return None, None, None


if __name__ == "__main__":
    results = asyncio.run(main())
