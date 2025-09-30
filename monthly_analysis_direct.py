#!/usr/bin/env python3
"""
Упрощенный помесячный анализ WB за 2025 год
Использует прямые вызовы get_real_wb_data без parallel_processor
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
from real_data_reports import RealDataFinancialReports

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DirectMonthlyAnalyzer:
    """Анализатор помесячных данных через прямые вызовы"""

    def __init__(self):
        self.real_reports = RealDataFinancialReports()
        self.monthly_data = {}

    async def analyze_months_direct(self):
        """Анализ месяцев через прямые вызовы get_real_wb_data"""

        logger.info("🔍 ПРЯМОЙ ПОМЕСЯЧНЫЙ АНАЛИЗ WB ЗА 2025 ГОД")
        logger.info("=" * 60)

        # Месяцы для анализа
        months = [
            ("2025-01-01", "2025-01-31", "Январь"),
            ("2025-02-01", "2025-02-28", "Февраль"),
            ("2025-03-01", "2025-03-31", "Март"),
            ("2025-04-01", "2025-04-30", "Апрель"),
            ("2025-05-01", "2025-05-31", "Май"),
            ("2025-06-01", "2025-06-30", "Июнь"),
            ("2025-07-01", "2025-07-31", "Июль"),
            ("2025-08-01", "2025-08-31", "Август"),
            ("2025-09-01", "2025-09-26", "Сентябрь (до 26.09)")
        ]

        total_revenue = 0
        total_units = 0
        monthly_results = []

        for date_from, date_to, month_name in months:
            logger.info(f"\n📅 Анализируем {month_name} ({date_from} - {date_to})")

            try:
                # Прямой вызов get_real_wb_data
                wb_data = await self.real_reports.get_real_wb_data(date_from, date_to)

                month_revenue = wb_data.get('revenue', 0)
                month_units = wb_data.get('units', 0)
                month_commission = wb_data.get('commission', 0)
                month_cogs = wb_data.get('cogs', 0)
                month_profit = wb_data.get('profit', 0)

                # Дополнительная диагностика
                orders_stats = wb_data.get('orders_stats', {})
                sales_stats = wb_data.get('sales_stats', {})

                monthly_result = {
                    'month': month_name,
                    'date_from': date_from,
                    'date_to': date_to,
                    'revenue': month_revenue,
                    'units': month_units,
                    'commission': month_commission,
                    'cogs': month_cogs,
                    'profit': month_profit,
                    'orders_count': orders_stats.get('count', 0),
                    'orders_revenue': orders_stats.get('price_with_disc', 0),
                    'sales_count': sales_stats.get('count', 0),
                    'sales_revenue': sales_stats.get('price_with_disc', 0),
                    'buyout_rate': (sales_stats.get('count', 0) / orders_stats.get('count', 1)) * 100 if orders_stats.get('count', 0) > 0 else 0
                }

                monthly_results.append(monthly_result)

                total_revenue += month_revenue
                total_units += month_units

                logger.info(f"✅ {month_name}:")
                logger.info(f"   💰 Выручка: {month_revenue:,.0f} ₽")
                logger.info(f"   📦 Единиц: {month_units:,.0f} шт")
                logger.info(f"   🛒 Заказов: {orders_stats.get('count', 0):,.0f}")
                logger.info(f"   ✅ Продаж: {sales_stats.get('count', 0):,.0f}")
                if orders_stats.get('count', 0) > 0:
                    buyout_rate = (sales_stats.get('count', 0) / orders_stats.get('count', 0)) * 100
                    logger.info(f"   📈 Выкуп: {buyout_rate:.1f}%")
                logger.info(f"   💳 Комиссия: {month_commission:,.0f} ₽")
                logger.info(f"   💲 Прибыль: {month_profit:,.0f} ₽")

            except Exception as e:
                logger.error(f"❌ Ошибка обработки {month_name}: {e}")
                monthly_result = {
                    'month': month_name,
                    'date_from': date_from,
                    'date_to': date_to,
                    'error': str(e),
                    'revenue': 0,
                    'units': 0
                }
                monthly_results.append(monthly_result)

        # Сохраняем детальные результаты
        self.monthly_data = {
            'analysis_date': datetime.now().isoformat(),
            'total_period': "2025-01-01 до 2025-09-26",
            'total_revenue': total_revenue,
            'total_units': total_units,
            'expected_revenue': 530000,  # Ожидания пользователя
            'discrepancy_ratio': total_revenue / 530000 if total_revenue > 0 else 0,
            'monthly_breakdown': monthly_results,
            'analysis_method': 'direct_wb_calls'
        }

        # Выводим итоги
        logger.info(f"\n" + "=" * 60)
        logger.info(f"📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ ЗА 2025 ГОД:")
        logger.info(f"💰 Общая выручка WB: {total_revenue:,.0f} ₽")
        logger.info(f"📦 Общие единицы: {total_units:,.0f} шт")
        logger.info(f"🎯 Ожидания пользователя: 530,000 ₽")
        logger.info(f"📈 Соотношение: {total_revenue/530000:.1f}x")
        logger.info(f"📉 Расхождение: {total_revenue - 530000:,.0f} ₽")

        return self.monthly_data

    def analyze_discrepancies_detailed(self):
        """Детальный анализ причин расхождений"""

        logger.info(f"\n🔍 ДЕТАЛЬНЫЙ АНАЛИЗ РАСХОЖДЕНИЙ:")
        logger.info(f"=" * 50)

        if not self.monthly_data:
            logger.error("Нет данных для анализа")
            return

        total_revenue = self.monthly_data['total_revenue']
        expected = self.monthly_data['expected_revenue']
        ratio = self.monthly_data['discrepancy_ratio']

        logger.info(f"📊 Фактическая выручка: {total_revenue:,.0f} ₽")
        logger.info(f"🎯 Ожидаемая выручка: {expected:,.0f} ₽")
        logger.info(f"📈 Превышение в {ratio:.1f} раза")

        # Помесячная разбивка с процентами
        monthly_breakdown = self.monthly_data['monthly_breakdown']
        expected_monthly = expected / 9  # Ожидаемая сумма в месяц

        logger.info(f"\n📅 ПОМЕСЯЧНАЯ РАЗБИВКА:")
        for month_data in monthly_breakdown:
            if 'error' not in month_data:
                month_revenue = month_data['revenue']
                month_ratio = month_revenue / expected_monthly if expected_monthly > 0 else 0
                percentage_of_total = (month_revenue / total_revenue) * 100 if total_revenue > 0 else 0

                logger.info(f"   {month_data['month']:15} | {month_revenue:>8,.0f} ₽ | {month_ratio:>4.1f}x ожид. | {percentage_of_total:>4.1f}% от общей")

        # Анализ заказов vs продаж
        total_orders = sum(m.get('orders_count', 0) for m in monthly_breakdown if 'error' not in m)
        total_sales = sum(m.get('sales_count', 0) for m in monthly_breakdown if 'error' not in m)
        total_orders_revenue = sum(m.get('orders_revenue', 0) for m in monthly_breakdown if 'error' not in m)
        total_sales_revenue = sum(m.get('sales_revenue', 0) for m in monthly_breakdown if 'error' not in m)

        logger.info(f"\n📊 АНАЛИЗ ЗАКАЗОВ vs ПРОДАЖ:")
        logger.info(f"   🛒 Всего заказов: {total_orders:,.0f} шт на {total_orders_revenue:,.0f} ₽")
        logger.info(f"   ✅ Всего продаж: {total_sales:,.0f} шт на {total_sales_revenue:,.0f} ₽")
        if total_orders > 0:
            overall_buyout = (total_sales / total_orders) * 100
            logger.info(f"   📈 Общий процент выкупа: {overall_buyout:.1f}%")

        # Сезонность
        logger.info(f"\n🌍 СЕЗОННЫЙ АНАЛИЗ:")
        q1_revenue = sum(m['revenue'] for m in monthly_breakdown[:3] if 'error' not in m)  # Янв-Мар
        q2_revenue = sum(m['revenue'] for m in monthly_breakdown[3:6] if 'error' not in m)  # Апр-Июн
        q3_revenue = sum(m['revenue'] for m in monthly_breakdown[6:9] if 'error' not in m)  # Июл-Сен

        logger.info(f"   Q1 (Янв-Мар): {q1_revenue:,.0f} ₽ ({(q1_revenue/total_revenue)*100:.1f}%)")
        logger.info(f"   Q2 (Апр-Июн): {q2_revenue:,.0f} ₽ ({(q2_revenue/total_revenue)*100:.1f}%)")
        logger.info(f"   Q3 (Июл-Сен): {q3_revenue:,.0f} ₽ ({(q3_revenue/total_revenue)*100:.1f}%)")

        # Средние показатели
        avg_monthly_revenue = total_revenue / 9
        avg_monthly_units = self.monthly_data['total_units'] / 9

        logger.info(f"\n📈 СРЕДНИЕ ПОКАЗАТЕЛИ:")
        logger.info(f"   💰 Средняя выручка в месяц: {avg_monthly_revenue:,.0f} ₽")
        logger.info(f"   📦 Средние единицы в месяц: {avg_monthly_units:,.0f} шт")

        # Возможные причины расхождений
        logger.info(f"\n🤔 ВОЗМОЖНЫЕ ПРИЧИНЫ РАСХОЖДЕНИЙ:")
        logger.info(f"1️⃣ МЕТОДИКА ПОДСЧЕТА:")
        logger.info(f"   ✅ Система: priceWithDisc (цена со скидками)")
        logger.info(f"   ✅ Источник: Sales API (только реальные выкупы)")
        logger.info(f"   ✅ Фильтр: isRealization = true")

        logger.info(f"2️⃣ ПЕРИОД АНАЛИЗА:")
        logger.info(f"   📅 Системный: 01.01.2025 - 26.09.2025 (268 дней)")
        logger.info(f"   💭 Возможно пользователь ожидал другой период?")

        logger.info(f"3️⃣ ПЛАТФОРМЫ:")
        logger.info(f"   🟣 Система: только Wildberries")
        logger.info(f"   💭 Возможно ожидался WB + Ozon?")

        logger.info(f"4️⃣ ТИП ДАННЫХ:")
        logger.info(f"   📊 Система показывает: {total_revenue:,.0f} ₽ реальной выручки")
        logger.info(f"   💭 Пользователь ожидал: 530,000 ₽")
        logger.info(f"   📈 Превышение в {ratio:.1f} раза может быть корректным")

        return {
            'total_revenue': total_revenue,
            'expected_revenue': expected,
            'discrepancy_ratio': ratio,
            'total_orders': total_orders,
            'total_sales': total_sales,
            'overall_buyout_rate': (total_sales / total_orders) * 100 if total_orders > 0 else 0,
            'q1_revenue': q1_revenue,
            'q2_revenue': q2_revenue,
            'q3_revenue': q3_revenue
        }

    def save_detailed_report(self):
        """Сохранение детального отчета"""

        filename = f"monthly_analysis_direct_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"/root/sovani_bot/reports/{filename}"

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.monthly_data, f, ensure_ascii=False, indent=2)

            logger.info(f"💾 Детальный отчет сохранен: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения отчета: {e}")
            return None

async def main():
    """Основная функция анализа"""

    analyzer = DirectMonthlyAnalyzer()

    # Проводим прямой помесячный анализ
    results = await analyzer.analyze_months_direct()

    # Проводим детальный анализ расхождений
    discrepancy_analysis = analyzer.analyze_discrepancies_detailed()

    # Сохраняем отчет
    report_path = analyzer.save_detailed_report()

    logger.info(f"\n🎯 ДЕТАЛЬНЫЙ АНАЛИЗ ЗАВЕРШЕН!")
    logger.info(f"📄 Отчет: {report_path}")

    return results, discrepancy_analysis

if __name__ == "__main__":
    results, analysis = asyncio.run(main())