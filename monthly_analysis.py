#!/usr/bin/env python3
"""Помесячный анализ данных WB за 2025 год
Детальное сравнение с ожиданиями пользователя
"""

import asyncio
import json
import logging
from datetime import datetime

from real_data_reports import RealDataFinancialReports

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MonthlyAnalyzer:
    """Анализатор помесячных данных"""

    def __init__(self):
        self.real_reports = RealDataFinancialReports()
        self.monthly_data = {}

    async def analyze_all_months_2025(self):
        """Анализ всех месяцев 2025 года"""
        logger.info("🔍 ДЕТАЛЬНЫЙ ПОМЕСЯЧНЫЙ АНАЛИЗ WB ЗА 2025 ГОД")
        logger.info("=" * 60)

        # Месяцы для анализа (до сентября включительно)
        months = [
            ("2025-01-01", "2025-01-31", "Январь"),
            ("2025-02-01", "2025-02-28", "Февраль"),
            ("2025-03-01", "2025-03-31", "Март"),
            ("2025-04-01", "2025-04-30", "Апрель"),
            ("2025-05-01", "2025-05-31", "Май"),
            ("2025-06-01", "2025-06-30", "Июнь"),
            ("2025-07-01", "2025-07-31", "Июль"),
            ("2025-08-01", "2025-08-31", "Август"),
            ("2025-09-01", "2025-09-26", "Сентябрь (до 26.09)"),
        ]

        total_revenue = 0
        total_units = 0
        monthly_results = []

        for date_from, date_to, month_name in months:
            logger.info(f"\n📅 Анализируем {month_name} ({date_from} - {date_to})")

            try:
                # Получаем данные только по WB
                result = await self.real_reports.calculate_real_pnl(
                    date_from, date_to, platform_filter="wb"
                )

                wb_data = result["wb"]
                month_revenue = wb_data["revenue"]
                month_units = wb_data["units"]
                month_commission = wb_data.get("commission", 0)
                month_profit = wb_data.get("profit", 0)
                processing_time = result.get("processing_time", 0)

                # Дополнительная диагностика
                orders_stats = wb_data.get("orders_stats", {})
                sales_stats = wb_data.get("sales_stats", {})

                monthly_result = {
                    "month": month_name,
                    "date_from": date_from,
                    "date_to": date_to,
                    "revenue": month_revenue,
                    "units": month_units,
                    "commission": month_commission,
                    "profit": month_profit,
                    "processing_time": processing_time,
                    "orders_count": orders_stats.get("count", 0),
                    "orders_revenue": orders_stats.get("price_with_disc", 0),
                    "sales_count": sales_stats.get("count", 0),
                    "sales_revenue": sales_stats.get("price_with_disc", 0),
                    "buyout_rate": (
                        (sales_stats.get("count", 0) / orders_stats.get("count", 1)) * 100
                        if orders_stats.get("count", 0) > 0
                        else 0
                    ),
                }

                monthly_results.append(monthly_result)

                total_revenue += month_revenue
                total_units += month_units

                logger.info(f"✅ {month_name}:")
                logger.info(f"   💰 Выручка: {month_revenue:,.0f} ₽")
                logger.info(f"   📦 Единиц: {month_units:,.0f} шт")
                logger.info(f"   🛒 Заказов: {orders_stats.get('count', 0):,.0f}")
                logger.info(f"   ✅ Продаж: {sales_stats.get('count', 0):,.0f}")
                if orders_stats.get("count", 0) > 0:
                    buyout_rate = (sales_stats.get("count", 0) / orders_stats.get("count", 0)) * 100
                    logger.info(f"   📈 Выкуп: {buyout_rate:.1f}%")
                logger.info(f"   ⏱️ Время: {processing_time:.1f}с")

            except Exception as e:
                logger.error(f"❌ Ошибка обработки {month_name}: {e}")
                monthly_result = {
                    "month": month_name,
                    "date_from": date_from,
                    "date_to": date_to,
                    "error": str(e),
                    "revenue": 0,
                    "units": 0,
                }
                monthly_results.append(monthly_result)

        # Сохраняем детальные результаты
        self.monthly_data = {
            "analysis_date": datetime.now().isoformat(),
            "total_period": "2025-01-01 до 2025-09-26",
            "total_revenue": total_revenue,
            "total_units": total_units,
            "expected_revenue": 530000,  # Ожидания пользователя
            "discrepancy_ratio": total_revenue / 530000 if total_revenue > 0 else 0,
            "monthly_breakdown": monthly_results,
        }

        # Выводим итоги
        logger.info("\n" + "=" * 60)
        logger.info("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ ЗА 2025 ГОД:")
        logger.info(f"💰 Общая выручка WB: {total_revenue:,.0f} ₽")
        logger.info(f"📦 Общие единицы: {total_units:,.0f} шт")
        logger.info("🎯 Ожидания пользователя: 530,000 ₽")
        logger.info(f"📈 Соотношение: {total_revenue/530000:.1f}x")
        logger.info(f"📉 Расхождение: {total_revenue - 530000:,.0f} ₽")

        return self.monthly_data

    def save_analysis_report(self):
        """Сохранение детального отчета"""
        filename = f"monthly_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"/root/sovani_bot/reports/{filename}"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.monthly_data, f, ensure_ascii=False, indent=2)

            logger.info(f"💾 Отчет сохранен: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения отчета: {e}")
            return None

    def analyze_discrepancies(self):
        """Анализ причин расхождений"""
        logger.info("\n🔍 АНАЛИЗ ПРИЧИН РАСХОЖДЕНИЙ:")
        logger.info("=" * 40)

        if not self.monthly_data:
            logger.error("Нет данных для анализа")
            return

        total_revenue = self.monthly_data["total_revenue"]
        expected = self.monthly_data["expected_revenue"]
        ratio = self.monthly_data["discrepancy_ratio"]

        logger.info(f"📊 Фактическая выручка: {total_revenue:,.0f} ₽")
        logger.info(f"🎯 Ожидаемая выручка: {expected:,.0f} ₽")
        logger.info(f"📈 Превышение в {ratio:.1f} раза")

        # Анализ помесячных данных
        monthly_breakdown = self.monthly_data["monthly_breakdown"]

        logger.info("\n📅 ПОМЕСЯЧНАЯ РАЗБИВКА:")
        for month_data in monthly_breakdown:
            if "error" not in month_data:
                month_avg = month_data["revenue"] / (530000 / 9)  # Средний ожидаемый месяц
                logger.info(
                    f"   {month_data['month']}: {month_data['revenue']:,.0f} ₽ (соотношение: {month_avg:.1f}x)"
                )

        # Возможные причины расхождений
        logger.info("\n🤔 ВОЗМОЖНЫЕ ПРИЧИНЫ РАСХОЖДЕНИЙ:")

        # 1. Методика подсчета
        total_orders = sum(m.get("orders_count", 0) for m in monthly_breakdown if "error" not in m)
        total_sales = sum(m.get("sales_count", 0) for m in monthly_breakdown if "error" not in m)

        logger.info("1️⃣ МЕТОДИКА ПОДСЧЕТА:")
        logger.info(f"   📋 Всего заказов: {total_orders:,.0f}")
        logger.info(f"   ✅ Всего продаж: {total_sales:,.0f}")
        logger.info("   📊 Используется: priceWithDisc (цена со скидками)")
        logger.info("   🎯 Источник: Sales API (реальные выкупы)")

        if total_orders > total_sales * 2:
            logger.info("   ⚠️ МНОГО ЗАКАЗОВ vs ПРОДАЖ - возможно учитываются невыкупленные заказы")

        # 2. Период анализа
        logger.info("2️⃣ ПЕРИОД АНАЛИЗА:")
        logger.info("   📅 Системный: 01.01.2025 - 26.09.2025 (268 дней)")
        logger.info("   ❓ Пользователь ожидал: возможно другой период?")

        # 3. Платформы
        logger.info("3️⃣ ОХВАТ ПЛАТФОРМ:")
        logger.info("   🟣 Система: только Wildberries")
        logger.info("   ❓ Пользователь ожидал: только WB или WB+Ozon?")

        # 4. Типы операций
        logger.info("4️⃣ ТИПЫ ОПЕРАЦИЙ:")
        logger.info("   ✅ Система учитывает: isRealization = true")
        logger.info("   📊 Базовая цена: priceWithDisc (после скидки продавца)")
        logger.info("   ❓ Пользователь ожидал: возможно другую методику?")

        return {
            "total_revenue": total_revenue,
            "expected_revenue": expected,
            "discrepancy_ratio": ratio,
            "total_orders": total_orders,
            "total_sales": total_sales,
            "analysis_points": [
                "Система использует Sales API с priceWithDisc",
                "Учитываются только реализованные продажи (isRealization=true)",
                "Период: полных 268 дней 2025 года",
                "Платформа: только Wildberries",
                f"Превышение ожиданий в {ratio:.1f} раза может указывать на разную методику",
            ],
        }


async def main():
    """Основная функция анализа"""
    analyzer = MonthlyAnalyzer()

    # Проводим помесячный анализ
    results = await analyzer.analyze_all_months_2025()

    # Анализируем расхождения
    discrepancy_analysis = analyzer.analyze_discrepancies()

    # Сохраняем отчет
    report_path = analyzer.save_analysis_report()

    logger.info("\n🎯 АНАЛИЗ ЗАВЕРШЕН!")
    logger.info(f"📄 Детальный отчет: {report_path}")

    return results, discrepancy_analysis


if __name__ == "__main__":
    results, analysis = asyncio.run(main())
