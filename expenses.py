#!/usr/bin/env python3
"""Система управления расходами
Поддерживает постоянные и переменные расходы для точного расчета P&L
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ExpenseType(Enum):
    """Типы расходов"""

    FIXED = "fixed"  # Постоянные расходы (аренда, зарплаты, подписки)
    VARIABLE = "variable"  # Переменные расходы (% от продаж, за единицу товара)
    COMMISSION = "commission"  # Комиссии маркетплейсов
    LOGISTICS = "logistics"  # Логистические расходы
    PENALTY = "penalty"  # Штрафы и пени
    ADVERTISING = "advertising"  # Рекламные расходы
    OTHER = "other"  # Прочие расходы


class CalculationType(Enum):
    """Способы расчета переменных расходов"""

    FIXED_AMOUNT = "fixed_amount"  # Фиксированная сумма
    PERCENT_OF_REVENUE = "percent_revenue"  # Процент от выручки
    PER_UNIT = "per_unit"  # За единицу товара
    PER_ORDER = "per_order"  # За заказ


@dataclass
class Expense:
    """Структура расхода"""

    id: str
    name: str
    expense_type: ExpenseType
    calculation_type: CalculationType
    amount: float  # Сумма или процент в зависимости от типа расчета
    platform: str | None = None  # wb, ozon, both, или None для общих расходов
    category: str | None = None  # Категория для группировки
    description: str = ""
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


class ExpenseManager:
    """Менеджер расходов"""

    def __init__(self, data_file: str = "data/expenses.json"):
        self.data_file = data_file
        self.expenses: dict[str, Expense] = {}
        self._ensure_data_dir()
        self._load_expenses()

    def _ensure_data_dir(self):
        """Создание директории для данных"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

    def _load_expenses(self):
        """Загрузка расходов из файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, encoding="utf-8") as f:
                    data = json.load(f)

                for expense_id, expense_data in data.items():
                    # Конвертируем enum'ы из строк
                    expense_data["expense_type"] = ExpenseType(expense_data["expense_type"])
                    expense_data["calculation_type"] = CalculationType(
                        expense_data["calculation_type"]
                    )
                    self.expenses[expense_id] = Expense(**expense_data)

                logger.info(f"Загружено {len(self.expenses)} расходов")
        except Exception as e:
            logger.error(f"Ошибка загрузки расходов: {e}")

    def _save_expenses(self):
        """Сохранение расходов в файл"""
        try:
            data = {}
            for expense_id, expense in self.expenses.items():
                expense_dict = asdict(expense)
                # Конвертируем enum'ы в строки для JSON
                expense_dict["expense_type"] = expense.expense_type.value
                expense_dict["calculation_type"] = expense.calculation_type.value
                data[expense_id] = expense_dict

            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Сохранено {len(self.expenses)} расходов")
        except Exception as e:
            logger.error(f"Ошибка сохранения расходов: {e}")

    def add_expense(
        self,
        name: str,
        expense_type: ExpenseType,
        calculation_type: CalculationType,
        amount: float,
        platform: str | None = None,
        category: str | None = None,
        description: str = "",
    ) -> str:
        """Добавление нового расхода

        Returns:
            ID созданного расхода

        """
        expense_id = f"exp_{int(datetime.now().timestamp() * 1000)}"

        expense = Expense(
            id=expense_id,
            name=name,
            expense_type=expense_type,
            calculation_type=calculation_type,
            amount=amount,
            platform=platform,
            category=category,
            description=description,
        )

        self.expenses[expense_id] = expense
        self._save_expenses()

        logger.info(f"Добавлен расход: {name} ({expense_type.value})")
        return expense_id

    def update_expense(self, expense_id: str, **kwargs) -> bool:
        """Обновление расхода"""
        if expense_id not in self.expenses:
            return False

        expense = self.expenses[expense_id]

        # Обновляем только переданные поля
        for key, value in kwargs.items():
            if hasattr(expense, key):
                setattr(expense, key, value)

        expense.updated_at = datetime.now().isoformat()
        self._save_expenses()

        logger.info(f"Обновлен расход: {expense_id}")
        return True

    def delete_expense(self, expense_id: str) -> bool:
        """Удаление расхода"""
        if expense_id not in self.expenses:
            return False

        expense_name = self.expenses[expense_id].name
        del self.expenses[expense_id]
        self._save_expenses()

        logger.info(f"Удален расход: {expense_name}")
        return True

    def get_expense(self, expense_id: str) -> Expense | None:
        """Получение расхода по ID"""
        return self.expenses.get(expense_id)

    def list_expenses(
        self,
        platform: str | None = None,
        expense_type: ExpenseType | None = None,
        active_only: bool = True,
    ) -> list[Expense]:
        """Список расходов с фильтрацией

        Args:
            platform: Фильтр по платформе (wb, ozon, both)
            expense_type: Фильтр по типу расхода
            active_only: Только активные расходы

        """
        expenses = list(self.expenses.values())

        if active_only:
            expenses = [e for e in expenses if e.is_active]

        if platform:
            expenses = [e for e in expenses if e.platform in [platform, "both", None]]

        if expense_type:
            expenses = [e for e in expenses if e.expense_type == expense_type]

        return sorted(expenses, key=lambda x: x.name)

    def calculate_expenses(
        self, revenue_data: dict[str, Any], units_sold: dict[str, int], orders_count: dict[str, int]
    ) -> dict[str, Any]:
        """Расчет всех расходов на основе данных о продажах

        Args:
            revenue_data: {'wb': revenue, 'ozon': revenue, 'total': revenue}
            units_sold: {'wb': units, 'ozon': units, 'total': units}
            orders_count: {'wb': orders, 'ozon': orders, 'total': orders}

        Returns:
            Детализированные расходы по категориям

        """
        result = {
            "total_expenses": 0.0,
            "by_platform": {"wb": 0.0, "ozon": 0.0, "both": 0.0},
            "by_type": {},
            "by_category": {},
            "detailed": [],
        }

        for expense in self.expenses.values():
            if not expense.is_active:
                continue

            calculated_amount = self._calculate_expense_amount(
                expense, revenue_data, units_sold, orders_count
            )

            if calculated_amount > 0:
                # Общие расходы
                result["total_expenses"] += calculated_amount

                # По платформам
                platform_key = expense.platform or "both"
                result["by_platform"][platform_key] += calculated_amount

                # По типам
                type_key = expense.expense_type.value
                if type_key not in result["by_type"]:
                    result["by_type"][type_key] = 0.0
                result["by_type"][type_key] += calculated_amount

                # По категориям
                category_key = expense.category or "other"
                if category_key not in result["by_category"]:
                    result["by_category"][category_key] = 0.0
                result["by_category"][category_key] += calculated_amount

                # Детализация
                result["detailed"].append(
                    {
                        "id": expense.id,
                        "name": expense.name,
                        "type": expense.expense_type.value,
                        "calculation_type": expense.calculation_type.value,
                        "base_amount": expense.amount,
                        "calculated_amount": calculated_amount,
                        "platform": expense.platform,
                        "category": expense.category,
                    }
                )

        return result

    def _calculate_expense_amount(
        self,
        expense: Expense,
        revenue_data: dict[str, Any],
        units_sold: dict[str, int],
        orders_count: dict[str, int],
    ) -> float:
        """Расчет суммы конкретного расхода"""
        if expense.calculation_type == CalculationType.FIXED_AMOUNT:
            return expense.amount

        elif expense.calculation_type == CalculationType.PERCENT_OF_REVENUE:
            # Определяем к какой выручке применить процент
            if expense.platform == "wb":
                base_revenue = revenue_data.get("wb", 0)
            elif expense.platform == "ozon":
                base_revenue = revenue_data.get("ozon", 0)
            else:
                base_revenue = revenue_data.get("total", 0)

            return base_revenue * (expense.amount / 100)

        elif expense.calculation_type == CalculationType.PER_UNIT:
            # Определяем количество единиц
            if expense.platform == "wb":
                base_units = units_sold.get("wb", 0)
            elif expense.platform == "ozon":
                base_units = units_sold.get("ozon", 0)
            else:
                base_units = units_sold.get("total", 0)

            return base_units * expense.amount

        elif expense.calculation_type == CalculationType.PER_ORDER:
            # Определяем количество заказов
            if expense.platform == "wb":
                base_orders = orders_count.get("wb", 0)
            elif expense.platform == "ozon":
                base_orders = orders_count.get("ozon", 0)
            else:
                base_orders = orders_count.get("total", 0)

            return base_orders * expense.amount

        return 0.0

    def get_expense_summary(self, platform: str | None = None) -> dict[str, Any]:
        """Сводка по расходам"""
        expenses = self.list_expenses(platform=platform, active_only=True)

        summary = {
            "total_count": len(expenses),
            "by_type": {},
            "by_calculation": {},
            "monthly_fixed": 0.0,
        }

        for expense in expenses:
            # По типам
            type_key = expense.expense_type.value
            if type_key not in summary["by_type"]:
                summary["by_type"][type_key] = 0
            summary["by_type"][type_key] += 1

            # По способу расчета
            calc_key = expense.calculation_type.value
            if calc_key not in summary["by_calculation"]:
                summary["by_calculation"][calc_key] = 0
            summary["by_calculation"][calc_key] += 1

            # Месячные фиксированные расходы
            if expense.calculation_type == CalculationType.FIXED_AMOUNT:
                summary["monthly_fixed"] += expense.amount

        return summary


# Предустановленные шаблоны расходов
DEFAULT_EXPENSES = [
    {
        "name": "Комиссия WB",
        "expense_type": ExpenseType.COMMISSION,
        "calculation_type": CalculationType.PERCENT_OF_REVENUE,
        "amount": 15.0,  # 15%
        "platform": "wb",
        "category": "marketplace_fees",
        "description": "Стандартная комиссия Wildberries",
    },
    {
        "name": "Комиссия Ozon",
        "expense_type": ExpenseType.COMMISSION,
        "calculation_type": CalculationType.PERCENT_OF_REVENUE,
        "amount": 12.0,  # 12%
        "platform": "ozon",
        "category": "marketplace_fees",
        "description": "Стандартная комиссия Ozon",
    },
    {
        "name": "Логистика за единицу",
        "expense_type": ExpenseType.LOGISTICS,
        "calculation_type": CalculationType.PER_UNIT,
        "amount": 150.0,  # 150₽ за единицу
        "platform": "both",
        "category": "logistics",
        "description": "Средняя стоимость логистики за единицу товара",
    },
    {
        "name": "Аренда склада",
        "expense_type": ExpenseType.FIXED,
        "calculation_type": CalculationType.FIXED_AMOUNT,
        "amount": 50000.0,  # 50,000₽ в месяц
        "platform": None,
        "category": "fixed_costs",
        "description": "Месячная аренда складского помещения",
    },
]


def initialize_default_expenses(expense_manager: ExpenseManager):
    """Инициализация стандартных расходов"""
    existing_count = len(expense_manager.list_expenses())

    if existing_count == 0:
        logger.info("Инициализация стандартных расходов...")

        for expense_data in DEFAULT_EXPENSES:
            expense_manager.add_expense(**expense_data)

        logger.info(f"Добавлено {len(DEFAULT_EXPENSES)} стандартных расходов")
