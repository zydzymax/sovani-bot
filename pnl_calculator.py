#!/usr/bin/env python3
"""
Калькулятор P&L с интеграцией реальных расходов из API
Объединяет данные о выручке, COGS и всех типах расходов
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json

from api_clients.ozon.sales_client import OzonSalesClient
from api_clients.wb.stats_client import WBStatsClient
from expenses import ExpenseManager
from expense_analyzer import ExpenseAnalyzer

logger = logging.getLogger(__name__)

@dataclass
class PnLData:
    """Структура данных P&L"""
    # Выручка
    total_revenue: float = 0.0
    wb_revenue: float = 0.0
    ozon_revenue: float = 0.0

    # Единицы товара
    total_units: int = 0
    wb_units: int = 0
    ozon_units: int = 0

    # COGS (себестоимость)
    total_cogs: float = 0.0

    # Расходы по категориям
    marketplace_commissions: float = 0.0
    logistics_costs: float = 0.0
    advertising_costs: float = 0.0
    penalties: float = 0.0
    fixed_costs: float = 0.0
    other_expenses: float = 0.0

    # Итоговые показатели
    gross_profit: float = 0.0  # Валовая прибыль (выручка - COGS)
    total_expenses: float = 0.0
    net_profit: float = 0.0  # Чистая прибыль

    # Маржинальность
    gross_margin_percent: float = 0.0
    net_margin_percent: float = 0.0

    # Метаданные
    period_from: str = ""
    period_to: str = ""
    generated_at: str = ""

class PnLCalculator:
    """Калькулятор прибылей и убытков"""

    def __init__(self, expense_manager: ExpenseManager, expense_analyzer: ExpenseAnalyzer):
        self.expense_manager = expense_manager
        self.expense_analyzer = expense_analyzer
        self.ozon_client = OzonSalesClient()
        self.wb_client = WBStatsClient()

    async def calculate_pnl(self, date_from: date, date_to: date,
                           cost_per_unit: float = 0.0) -> PnLData:
        """
        Расчет полного P&L отчета

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            cost_per_unit: Себестоимость за единицу товара

        Returns:
            Структура с данными P&L
        """
        pnl = PnLData(
            period_from=date_from.isoformat(),
            period_to=date_to.isoformat(),
            generated_at=datetime.now().isoformat()
        )

        # 1. Получаем данные о выручке
        await self._calculate_revenue(pnl, date_from, date_to)

        # 2. Рассчитываем COGS
        pnl.total_cogs = pnl.total_units * cost_per_unit

        # 3. Получаем реальные расходы из API
        await self._calculate_api_expenses(pnl, date_from, date_to)

        # 4. Добавляем настроенные расходы из системы управления
        await self._calculate_configured_expenses(pnl)

        # 5. Рассчитываем итоговые показатели
        self._calculate_totals(pnl)

        logger.info(f"P&L рассчитан: выручка {pnl.total_revenue:,.0f} ₽, прибыль {pnl.net_profit:,.0f} ₽")
        return pnl

    async def _calculate_revenue(self, pnl: PnLData, date_from: date, date_to: date):
        """Расчет выручки по платформам"""

        # Ozon - используем новый клиент с разделением заказов/выкупов
        try:
            ozon_data = await self.ozon_client.get_revenue(date_from, date_to)
            pnl.ozon_revenue = ozon_data.get('delivered_revenue', 0.0)  # Только выкупы
            # Можно также получить общую сумму заказов: ozon_data.get('total_orders_revenue', 0.0)

            # Примерное количество единиц (если нет точных данных)
            ozon_delivered_count = ozon_data.get('delivered_count', 0)
            pnl.ozon_units = ozon_delivered_count

            logger.info(f"Ozon: выручка {pnl.ozon_revenue:,.0f} ₽, операций {ozon_delivered_count}")

        except Exception as e:
            logger.error(f"Ошибка получения данных Ozon: {e}")
            pnl.ozon_revenue = 0.0
            pnl.ozon_units = 0

        # WB - пока не работает из-за токена
        try:
            wb_sales = await self.wb_client.get_sales(date_from, date_to)
            pnl.wb_revenue = sum(sale.get('forPay', 0) for sale in wb_sales)
            pnl.wb_units = len(wb_sales)
            logger.info(f"WB: выручка {pnl.wb_revenue:,.0f} ₽, продаж {pnl.wb_units}")

        except Exception as e:
            logger.error(f"Ошибка получения данных WB: {e}")
            pnl.wb_revenue = 0.0
            pnl.wb_units = 0

        # Итого
        pnl.total_revenue = pnl.wb_revenue + pnl.ozon_revenue
        pnl.total_units = pnl.wb_units + pnl.ozon_units

    async def _calculate_api_expenses(self, pnl: PnLData, date_from: date, date_to: date):
        """Расчет реальных расходов из API транзакций"""

        try:
            # Анализируем расходы через API
            expense_report = await self.expense_analyzer.generate_expense_report(date_from, date_to)

            # Ozon расходы
            ozon_data = expense_report['platforms'].get('ozon', {})
            ozon_categories = ozon_data.get('categories', {})

            pnl.marketplace_commissions += ozon_categories.get('commission', 0.0)
            pnl.logistics_costs += ozon_categories.get('logistics', 0.0)
            pnl.advertising_costs += ozon_categories.get('advertising', 0.0)
            pnl.penalties += ozon_categories.get('penalties', 0.0)
            pnl.other_expenses += ozon_categories.get('returns', 0.0) + ozon_categories.get('other', 0.0)

            # WB расходы (когда API заработает)
            wb_data = expense_report['platforms'].get('wb', {})
            wb_categories = wb_data.get('categories', {})

            pnl.marketplace_commissions += wb_categories.get('commission', 0.0)
            pnl.logistics_costs += wb_categories.get('logistics', 0.0)
            pnl.advertising_costs += wb_categories.get('advertising', 0.0)
            pnl.penalties += wb_categories.get('penalties', 0.0)
            pnl.other_expenses += wb_categories.get('returns', 0.0) + wb_categories.get('other', 0.0)

            logger.info(f"API расходы: комиссии {pnl.marketplace_commissions:,.0f}, реклама {pnl.advertising_costs:,.0f}")

        except Exception as e:
            logger.error(f"Ошибка получения расходов из API: {e}")

    async def _calculate_configured_expenses(self, pnl: PnLData):
        """Расчет настроенных расходов из системы управления"""

        try:
            # Данные для расчета переменных расходов
            revenue_data = {
                'wb': pnl.wb_revenue,
                'ozon': pnl.ozon_revenue,
                'total': pnl.total_revenue
            }
            units_sold = {
                'wb': pnl.wb_units,
                'ozon': pnl.ozon_units,
                'total': pnl.total_units
            }
            orders_count = {
                'wb': pnl.wb_units,  # Примерно
                'ozon': pnl.ozon_units,  # Примерно
                'total': pnl.total_units
            }

            # Рассчитываем расходы
            calculated_expenses = self.expense_manager.calculate_expenses(
                revenue_data, units_sold, orders_count
            )

            # Добавляем к уже имеющимся расходам из API
            expense_by_type = calculated_expenses['by_type']

            pnl.fixed_costs += expense_by_type.get('fixed', 0.0)
            pnl.marketplace_commissions += expense_by_type.get('commission', 0.0)
            pnl.logistics_costs += expense_by_type.get('logistics', 0.0)
            pnl.advertising_costs += expense_by_type.get('advertising', 0.0)
            pnl.penalties += expense_by_type.get('penalty', 0.0)
            pnl.other_expenses += expense_by_type.get('other', 0.0)

            logger.info(f"Настроенные расходы: фиксированные {expense_by_type.get('fixed', 0):,.0f}")

        except Exception as e:
            logger.error(f"Ошибка расчета настроенных расходов: {e}")

    def _calculate_totals(self, pnl: PnLData):
        """Расчет итоговых показателей"""

        # Валовая прибыль (выручка - себестоимость)
        pnl.gross_profit = pnl.total_revenue - pnl.total_cogs

        # Общие расходы
        pnl.total_expenses = (
            pnl.marketplace_commissions +
            pnl.logistics_costs +
            pnl.advertising_costs +
            pnl.penalties +
            pnl.fixed_costs +
            pnl.other_expenses
        )

        # Чистая прибыль
        pnl.net_profit = pnl.gross_profit - pnl.total_expenses

        # Маржинальность
        if pnl.total_revenue > 0:
            pnl.gross_margin_percent = (pnl.gross_profit / pnl.total_revenue) * 100
            pnl.net_margin_percent = (pnl.net_profit / pnl.total_revenue) * 100

    def format_pnl_report(self, pnl: PnLData, detailed: bool = True) -> str:
        """Форматирование P&L отчета для вывода"""

        text = f"📊 <b>P&L Отчет</b>\n"
        text += f"📅 <b>{pnl.period_from} — {pnl.period_to}</b>\n\n"

        # Выручка
        text += f"💰 <b>ВЫРУЧКА</b>\n"
        text += f"🔵 Ozon: {pnl.ozon_revenue:,.0f} ₽\n"
        text += f"🟣 WB: {pnl.wb_revenue:,.0f} ₽\n"
        text += f"📊 <b>Итого: {pnl.total_revenue:,.0f} ₽</b>\n\n"

        # Себестоимость
        text += f"📦 <b>СЕБЕСТОИМОСТЬ</b>\n"
        text += f"Единиц продано: {pnl.total_units:,}\n"
        text += f"COGS: {pnl.total_cogs:,.0f} ₽\n"
        text += f"💚 <b>Валовая прибыль: {pnl.gross_profit:,.0f} ₽ ({pnl.gross_margin_percent:.1f}%)</b>\n\n"

        # Расходы
        text += f"💸 <b>РАСХОДЫ</b>\n"
        if detailed:
            text += f"💳 Комиссии маркетплейсов: {pnl.marketplace_commissions:,.0f} ₽\n"
            text += f"🚚 Логистика: {pnl.logistics_costs:,.0f} ₽\n"
            text += f"📢 Реклама: {pnl.advertising_costs:,.0f} ₽\n"
            text += f"⚠️ Штрафы: {pnl.penalties:,.0f} ₽\n"
            text += f"📌 Постоянные расходы: {pnl.fixed_costs:,.0f} ₽\n"
            text += f"📝 Прочие: {pnl.other_expenses:,.0f} ₽\n"
        text += f"📊 <b>Всего расходов: {pnl.total_expenses:,.0f} ₽</b>\n\n"

        # Итого
        profit_emoji = "💚" if pnl.net_profit >= 0 else "❌"
        text += f"{profit_emoji} <b>ЧИСТАЯ ПРИБЫЛЬ: {pnl.net_profit:,.0f} ₽ ({pnl.net_margin_percent:.1f}%)</b>\n\n"

        # Ключевые метрики
        if detailed:
            text += f"📈 <b>КЛЮЧЕВЫЕ МЕТРИКИ</b>\n"
            if pnl.total_units > 0:
                avg_revenue_per_unit = pnl.total_revenue / pnl.total_units
                avg_profit_per_unit = pnl.net_profit / pnl.total_units
                text += f"Средний чек: {avg_revenue_per_unit:,.0f} ₽\n"
                text += f"Прибыль на единицу: {avg_profit_per_unit:,.0f} ₽\n"

            if pnl.total_revenue > 0:
                expense_ratio = (pnl.total_expenses / pnl.total_revenue) * 100
                text += f"Доля расходов: {expense_ratio:.1f}%\n"

        text += f"\n<i>Сгенерировано: {datetime.now().strftime('%H:%M')}</i>"

        return text

    async def save_pnl_report(self, pnl: PnLData, filename: Optional[str] = None) -> str:
        """Сохранение P&L отчета в файл"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/pnl_report_{timestamp}.json"

        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # Конвертируем dataclass в dict для JSON
        pnl_dict = {
            'total_revenue': pnl.total_revenue,
            'wb_revenue': pnl.wb_revenue,
            'ozon_revenue': pnl.ozon_revenue,
            'total_units': pnl.total_units,
            'wb_units': pnl.wb_units,
            'ozon_units': pnl.ozon_units,
            'total_cogs': pnl.total_cogs,
            'marketplace_commissions': pnl.marketplace_commissions,
            'logistics_costs': pnl.logistics_costs,
            'advertising_costs': pnl.advertising_costs,
            'penalties': pnl.penalties,
            'fixed_costs': pnl.fixed_costs,
            'other_expenses': pnl.other_expenses,
            'gross_profit': pnl.gross_profit,
            'total_expenses': pnl.total_expenses,
            'net_profit': pnl.net_profit,
            'gross_margin_percent': pnl.gross_margin_percent,
            'net_margin_percent': pnl.net_margin_percent,
            'period_from': pnl.period_from,
            'period_to': pnl.period_to,
            'generated_at': pnl.generated_at
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(pnl_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"P&L отчет сохранен: {filename}")
        return filename

# Пример использования
async def main():
    """Тестирование P&L калькулятора"""
    from expenses import ExpenseManager
    from expense_analyzer import ExpenseAnalyzer

    expense_manager = ExpenseManager()
    expense_analyzer = ExpenseAnalyzer(expense_manager)
    calculator = PnLCalculator(expense_manager, expense_analyzer)

    # Рассчитываем P&L за последний месяц
    date_to = date.today()
    date_from = date_to - timedelta(days=30)
    cost_per_unit = 800.0  # Себестоимость 800₽ за единицу

    print("📊 Рассчитываем P&L отчет...")

    pnl = await calculator.calculate_pnl(date_from, date_to, cost_per_unit)

    print("\n" + calculator.format_pnl_report(pnl, detailed=True))

    # Сохраняем отчет
    filename = await calculator.save_pnl_report(pnl)
    print(f"\n✅ P&L отчет сохранен: {filename}")

if __name__ == "__main__":
    asyncio.run(main())