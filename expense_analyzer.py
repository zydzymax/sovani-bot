#!/usr/bin/env python3
"""
Анализатор расходов и штрафов из API маркетплейсов
Автоматически извлекает и классифицирует расходы
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json

from config import Config
from api_clients.ozon.sales_client import OzonSalesClient
from expenses import ExpenseManager, ExpenseType, CalculationType

logger = logging.getLogger(__name__)

@dataclass
class ExpenseRecord:
    """Запись о расходе из API"""
    platform: str
    operation_type: str
    amount: float
    date: str
    description: str
    posting_number: Optional[str] = None
    category: str = 'other'

@dataclass
class PenaltyAlert:
    """Уведомление о штрафе"""
    platform: str
    amount: float
    reason: str
    date: str
    posting_number: Optional[str] = None
    severity: str = 'medium'  # low, medium, high

class ExpenseAnalyzer:
    """Анализатор расходов маркетплейсов"""

    def __init__(self, expense_manager: ExpenseManager):
        self.expense_manager = expense_manager
        self.ozon_client = OzonSalesClient()

    async def analyze_ozon_expenses(self, date_from: date, date_to: date) -> Dict[str, Any]:
        """Анализ расходов Ozon через Transaction API"""

        try:
            transactions = await self.ozon_client.get_transactions(date_from, date_to)

            expenses = []
            penalties = []
            commissions = []
            logistics = []
            advertising = []
            other_expenses = []

            total_expenses = 0.0

            for transaction in transactions:
                op_type = transaction.get('operation_type', '')
                amount = float(transaction.get('amount', 0))
                date_str = transaction.get('operation_date', '')
                posting = transaction.get('posting', {})
                posting_number = posting.get('posting_number', '')

                # Только отрицательные суммы (расходы)
                if amount >= 0:
                    continue

                expense_amount = abs(amount)
                total_expenses += expense_amount

                # Классификация расходов
                expense_record = ExpenseRecord(
                    platform='ozon',
                    operation_type=op_type,
                    amount=expense_amount,
                    date=date_str,
                    description=self._get_operation_description(op_type),
                    posting_number=posting_number
                )

                # Штрафы и пени
                if any(word in op_type.lower() for word in ['penalty', 'fine', 'violation']):
                    expense_record.category = 'penalty'
                    penalties.append(expense_record)

                    # Создаем уведомление о штрафе
                    severity = self._determine_penalty_severity(expense_amount)
                    penalty_alert = PenaltyAlert(
                        platform='ozon',
                        amount=expense_amount,
                        reason=self._get_penalty_reason(op_type),
                        date=date_str,
                        posting_number=posting_number,
                        severity=severity
                    )
                    penalties.append(penalty_alert)

                # Комиссии и эквайринг
                elif any(word in op_type.lower() for word in ['acquiring', 'commission', 'marketplace']):
                    expense_record.category = 'commission'
                    commissions.append(expense_record)

                # Логистика
                elif any(word in op_type.lower() for word in ['delivery', 'logistics', 'shipping', 'package']):
                    expense_record.category = 'logistics'
                    logistics.append(expense_record)

                # Реклама и продвижение
                elif any(word in op_type.lower() for word in ['promotion', 'advertising', 'premium', 'top']):
                    expense_record.category = 'advertising'
                    advertising.append(expense_record)

                # Возвраты
                elif 'return' in op_type.lower():
                    expense_record.category = 'returns'
                    other_expenses.append(expense_record)

                # Прочие расходы
                else:
                    expense_record.category = 'other'
                    other_expenses.append(expense_record)

                expenses.append(expense_record)

            # Агрегация по категориям
            categories = {
                'penalties': sum(e.amount for e in expenses if e.category == 'penalty'),
                'commissions': sum(e.amount for e in expenses if e.category == 'commission'),
                'logistics': sum(e.amount for e in expenses if e.category == 'logistics'),
                'advertising': sum(e.amount for e in expenses if e.category == 'advertising'),
                'returns': sum(e.amount for e in expenses if e.category == 'returns'),
                'other': sum(e.amount for e in expenses if e.category == 'other')
            }

            result = {
                'platform': 'ozon',
                'period': {'from': date_from.isoformat(), 'to': date_to.isoformat()},
                'total_expenses': total_expenses,
                'expenses_count': len(expenses),
                'categories': categories,
                'penalties': {
                    'count': len([e for e in expenses if e.category == 'penalty']),
                    'total': categories['penalties'],
                    'alerts': [p for p in penalties if isinstance(p, PenaltyAlert)]
                },
                'top_expense_types': self._get_top_expense_types(expenses),
                'detailed_expenses': expenses
            }

            logger.info(f"Ozon: проанализировано {len(expenses)} расходов на сумму {total_expenses:,.2f} ₽")
            return result

        except Exception as e:
            logger.error(f"Ошибка анализа расходов Ozon: {e}")
            return {
                'platform': 'ozon',
                'error': str(e),
                'total_expenses': 0,
                'expenses_count': 0
            }

    def _get_operation_description(self, operation_type: str) -> str:
        """Получение описания операции на русском языке"""
        descriptions = {
            'OperationElectronicServiceStencil': 'Услуги по нанесению этикеток',
            'OperationPromotionWithCostPerOrder': 'Продвижение товара (за заказ)',
            'OperationItemReturn': 'Возврат товара',
            'ClientReturnAgentOperation': 'Операция возврата через агента',
            'OperationGettingToTheTop': 'Продвижение в топ поиска',
            'OperationSubscriptionPremium': 'Подписка Premium',
            'MarketplaceRedistributionOfAcquiringOperation': 'Комиссия за эквайринг',
            'OperationMarketplaceServicePremiumCashbackIndividualPoints': 'Кэшбэк Premium',
            'OperationMarketplacePackageRedistribution': 'Перераспределение упаковки',
            'OperationMarketplacePackageMaterialsProvision': 'Предоставление упаковочных материалов',
            'OperationAgentDeliveredToCustomer': 'Доставка клиенту'
        }
        return descriptions.get(operation_type, operation_type)

    def _get_penalty_reason(self, operation_type: str) -> str:
        """Определение причины штрафа"""
        if 'penalty' in operation_type.lower():
            return 'Штраф за нарушение условий'
        elif 'fine' in operation_type.lower():
            return 'Денежное взыскание'
        else:
            return 'Неопределенный штраф'

    def _determine_penalty_severity(self, amount: float) -> str:
        """Определение серьезности штрафа"""
        if amount < 1000:
            return 'low'
        elif amount < 5000:
            return 'medium'
        else:
            return 'high'

    def _get_top_expense_types(self, expenses: List[ExpenseRecord], limit: int = 5) -> List[Dict]:
        """Топ типов расходов"""
        type_totals = {}
        for expense in expenses:
            if expense.operation_type not in type_totals:
                type_totals[expense.operation_type] = {
                    'amount': 0,
                    'count': 0,
                    'description': expense.description
                }
            type_totals[expense.operation_type]['amount'] += expense.amount
            type_totals[expense.operation_type]['count'] += 1

        sorted_types = sorted(
            type_totals.items(),
            key=lambda x: x[1]['amount'],
            reverse=True
        )

        return [
            {
                'type': type_name,
                'amount': data['amount'],
                'count': data['count'],
                'description': data['description']
            }
            for type_name, data in sorted_types[:limit]
        ]

    async def get_penalty_alerts(self, days_back: int = 7) -> List[PenaltyAlert]:
        """Получение уведомлений о штрафах за последние дни"""
        date_to = date.today()
        date_from = date_to - timedelta(days=days_back)

        alerts = []

        # Анализируем Ozon
        ozon_analysis = await self.analyze_ozon_expenses(date_from, date_to)
        ozon_penalties = ozon_analysis.get('penalties', {}).get('alerts', [])
        alerts.extend(ozon_penalties)

        # TODO: Добавить анализ WB когда API заработает

        # Сортируем по серьезности и дате
        alerts.sort(key=lambda x: (
            {'high': 3, 'medium': 2, 'low': 1}[x.severity],
            x.date
        ), reverse=True)

        return alerts

    async def generate_expense_report(self, date_from: date, date_to: date) -> Dict[str, Any]:
        """Генерация отчета по расходам"""

        ozon_analysis = await self.analyze_ozon_expenses(date_from, date_to)

        # TODO: Добавить WB анализ когда API заработает
        wb_analysis = {
            'platform': 'wb',
            'total_expenses': 0,
            'expenses_count': 0,
            'categories': {},
            'error': 'WB API недоступен'
        }

        total_expenses = ozon_analysis.get('total_expenses', 0) + wb_analysis.get('total_expenses', 0)

        report = {
            'period': {'from': date_from.isoformat(), 'to': date_to.isoformat()},
            'total_expenses': total_expenses,
            'platforms': {
                'ozon': ozon_analysis,
                'wb': wb_analysis
            },
            'summary': {
                'penalties_total': ozon_analysis.get('penalties', {}).get('total', 0),
                'penalties_count': ozon_analysis.get('penalties', {}).get('count', 0),
                'top_categories': self._merge_categories([ozon_analysis, wb_analysis])
            },
            'generated_at': datetime.now().isoformat()
        }

        return report

    def _merge_categories(self, analyses: List[Dict]) -> Dict[str, float]:
        """Объединение категорий расходов из разных платформ"""
        merged = {}

        for analysis in analyses:
            categories = analysis.get('categories', {})
            for category, amount in categories.items():
                merged[category] = merged.get(category, 0) + amount

        # Сортируем по убыванию
        return dict(sorted(merged.items(), key=lambda x: x[1], reverse=True))

    async def save_expense_report(self, report: Dict[str, Any], filename: Optional[str] = None):
        """Сохранение отчета в файл"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/expense_report_{timestamp}.json"

        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Отчет о расходах сохранен: {filename}")
        return filename

# Пример использования
async def main():
    """Тестирование анализатора расходов"""
    from expenses import ExpenseManager

    expense_manager = ExpenseManager()
    analyzer = ExpenseAnalyzer(expense_manager)

    # Анализ за последний месяц
    date_to = date.today()
    date_from = date_to - timedelta(days=30)

    print("🔍 Генерируем отчет о расходах...")

    report = await analyzer.generate_expense_report(date_from, date_to)

    print(f"\n💰 Отчет о расходах за {date_from} - {date_to}:")
    print(f"Общие расходы: {report['total_expenses']:,.2f} ₽")

    print(f"\n📊 По платформам:")
    for platform, data in report['platforms'].items():
        total = data.get('total_expenses', 0)
        count = data.get('expenses_count', 0)
        print(f"  {platform.upper()}: {total:,.2f} ₽ ({count} операций)")

    print(f"\n⚠️ Штрафы:")
    penalties = report['summary']
    print(f"  Всего: {penalties['penalties_total']:,.2f} ₽ ({penalties['penalties_count']} штрафов)")

    # Сохраняем отчет
    filename = await analyzer.save_expense_report(report)
    print(f"\n✅ Отчет сохранен: {filename}")

    # Проверяем уведомления о штрафах
    alerts = await analyzer.get_penalty_alerts(days_back=30)
    if alerts:
        print(f"\n🚨 Уведомления о штрафах ({len(alerts)}):")
        for alert in alerts[:3]:  # Показываем только первые 3
            print(f"  {alert.platform.upper()}: {alert.amount:,.2f} ₽ - {alert.reason}")

if __name__ == "__main__":
    asyncio.run(main())