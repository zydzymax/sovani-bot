#!/usr/bin/env python3
"""
Система управления рекламными расходами
Позволяет вручную задавать и обновлять расходы на рекламу WB и Ozon
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from expenses import ExpenseManager, ExpenseType, CalculationType

logger = logging.getLogger(__name__)

class AdvertisingExpenseManager:
    """Менеджер рекламных расходов с ручным вводом"""

    def __init__(self):
        self.expense_manager = ExpenseManager()
        self.wb_ads_expense_id = None
        self.ozon_ads_expense_id = None
        self._init_advertising_expenses()

    def _init_advertising_expenses(self):
        """Инициализация рекламных расходов в системе"""
        # Ищем существующие рекламные расходы
        existing_expenses = self.expense_manager.list_expenses(expense_type=ExpenseType.ADVERTISING)

        wb_found = False
        ozon_found = False

        for expense in existing_expenses:
            if expense.platform == 'wb' and 'ручной ввод' in expense.name.lower():
                self.wb_ads_expense_id = expense.id
                wb_found = True
                logger.info(f"Найден существующий WB рекламный расход: {expense.id}")
            elif expense.platform == 'ozon' and 'ручной ввод' in expense.name.lower():
                self.ozon_ads_expense_id = expense.id
                ozon_found = True
                logger.info(f"Найден существующий Ozon рекламный расход: {expense.id}")

        # Создаем недостающие расходы
        if not wb_found:
            self.wb_ads_expense_id = self.expense_manager.add_expense(
                name='Реклама WB (ручной ввод)',
                expense_type=ExpenseType.ADVERTISING,
                calculation_type=CalculationType.FIXED_AMOUNT,
                amount=0.0,
                platform='wb',
                category='advertising',
                description='Ручной ввод рекламных расходов WB'
            )
            logger.info(f"Создан WB рекламный расход: {self.wb_ads_expense_id}")

        if not ozon_found:
            self.ozon_ads_expense_id = self.expense_manager.add_expense(
                name='Реклама Ozon (ручной ввод)',
                expense_type=ExpenseType.ADVERTISING,
                calculation_type=CalculationType.FIXED_AMOUNT,
                amount=0.0,
                platform='ozon',
                category='advertising',
                description='Ручной ввод рекламных расходов Ozon'
            )
            logger.info(f"Создан Ozon рекламный расход: {self.ozon_ads_expense_id}")

    def set_wb_advertising_expense(self, amount: float, period_description: str = "") -> bool:
        """
        Установка рекламных расходов WB

        Args:
            amount: Сумма расходов в рублях
            period_description: Описание периода (например, "январь 2025")
        """
        try:
            description = f"Реклама WB за {period_description}" if period_description else "Реклама WB (ручной ввод)"

            success = self.expense_manager.update_expense(
                self.wb_ads_expense_id,
                amount=amount,
                description=description
            )

            if success:
                logger.info(f"✅ WB реклама обновлена: {amount:,.2f} ₽ ({period_description})")
            else:
                logger.error(f"❌ Ошибка обновления WB рекламы")

            return success
        except Exception as e:
            logger.error(f"Ошибка установки WB рекламных расходов: {e}")
            return False

    def set_ozon_advertising_expense(self, amount: float, period_description: str = "") -> bool:
        """
        Установка рекламных расходов Ozon

        Args:
            amount: Сумма расходов в рублях
            period_description: Описание периода
        """
        try:
            description = f"Реклама Ozon за {period_description}" if period_description else "Реклама Ozon (ручной ввод)"

            success = self.expense_manager.update_expense(
                self.ozon_ads_expense_id,
                amount=amount,
                description=description
            )

            if success:
                logger.info(f"✅ Ozon реклама обновлена: {amount:,.2f} ₽ ({period_description})")
            else:
                logger.error(f"❌ Ошибка обновления Ozon рекламы")

            return success
        except Exception as e:
            logger.error(f"Ошибка установки Ozon рекламных расходов: {e}")
            return False

    def get_advertising_expenses(self) -> Dict[str, float]:
        """Получение текущих рекламных расходов"""
        wb_expense = self.expense_manager.get_expense(self.wb_ads_expense_id)
        ozon_expense = self.expense_manager.get_expense(self.ozon_ads_expense_id)

        return {
            'wb_advertising': wb_expense.amount if wb_expense else 0.0,
            'ozon_advertising': ozon_expense.amount if ozon_expense else 0.0,
            'total_advertising': (wb_expense.amount if wb_expense else 0.0) +
                               (ozon_expense.amount if ozon_expense else 0.0)
        }

    def reset_advertising_expenses(self) -> bool:
        """Сброс всех рекламных расходов в 0"""
        try:
            wb_success = self.set_wb_advertising_expense(0.0, "сброшено")
            ozon_success = self.set_ozon_advertising_expense(0.0, "сброшено")

            return wb_success and ozon_success
        except Exception as e:
            logger.error(f"Ошибка сброса рекламных расходов: {e}")
            return False

    def get_expense_summary(self) -> str:
        """Получение сводки по рекламным расходам"""
        expenses = self.get_advertising_expenses()

        return f"""📺 РЕКЛАМНЫЕ РАСХОДЫ:
• WB реклама: {expenses['wb_advertising']:,.0f} ₽
• Ozon реклама: {expenses['ozon_advertising']:,.0f} ₽
• <b>Итого реклама: {expenses['total_advertising']:,.0f} ₽</b>"""

# Глобальный экземпляр
advertising_manager = AdvertisingExpenseManager()

# Удобные функции для использования в боте
def set_wb_ads_expense(amount: float, period: str = "") -> bool:
    """Установить расходы на рекламу WB"""
    return advertising_manager.set_wb_advertising_expense(amount, period)

def set_ozon_ads_expense(amount: float, period: str = "") -> bool:
    """Установить расходы на рекламу Ozon"""
    return advertising_manager.set_ozon_advertising_expense(amount, period)

def get_ads_expenses() -> Dict[str, float]:
    """Получить все рекламные расходы"""
    return advertising_manager.get_advertising_expenses()

def reset_ads_expenses() -> bool:
    """Сбросить все рекламные расходы"""
    return advertising_manager.reset_advertising_expenses()