#!/usr/bin/env python3
"""
СИСТЕМА ВАЛИДАЦИИ ДАННЫХ
Автоматическая проверка качества и точности данных

Дата создания: 30 сентября 2025
Цель: Постоянный мониторинг качества данных и алертинг при аномалиях
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ValidationRule:
    """Правило валидации"""
    name: str
    description: str
    threshold: float  # Порог для алерта
    severity: str  # "error", "warning", "info"


@dataclass
class ValidationResult:
    """Результат проверки валидации"""
    rule_name: str
    passed: bool
    actual_value: float
    threshold: float
    severity: str
    message: str


class DataValidator:
    """
    Система валидации качества данных

    Проверки:
    1. Разумность сумм (не превышают ожидаемые в 2+ раза)
    2. Отсутствие дубликатов
    3. Корректность дат
    4. Соответствие историческим данным
    5. Правильность расчетов (forPay < priceWithDisc)
    """

    def __init__(self):
        # Эталонные данные для сравнения
        self.reference_data = {
            'january_2025': {
                'expected_revenue': 60688,  # forPay
                'expected_orders_value': 113595,  # priceWithDisc
                'tolerance': 0.05  # ±5%
            },
            '9_months_2025': {
                'expected_revenue': 530000,  # Целевое значение
                'tolerance': 0.05  # ±5%
            }
        }

        # Правила валидации
        self.rules = [
            ValidationRule(
                name="revenue_reasonableness",
                description="Выручка не превышает ожидаемую более чем в 2 раза",
                threshold=2.0,
                severity="error"
            ),
            ValidationRule(
                name="deduplication_quality",
                description="Процент дубликатов не превышает 10%",
                threshold=10.0,
                severity="warning"
            ),
            ValidationRule(
                name="date_filtering_quality",
                description="Записей вне периода менее 1%",
                threshold=1.0,
                severity="warning"
            ),
            ValidationRule(
                name="accuracy_vs_reference",
                description="Точность относительно эталона >= 95%",
                threshold=95.0,
                severity="error"
            ),
            ValidationRule(
                name="forpay_vs_pricewithdis",
                description="forPay всегда меньше priceWithDisc (удержания WB)",
                threshold=1.0,
                severity="error"
            )
        ]

    def validate_result(
        self,
        result: Dict[str, Any],
        reference_key: Optional[str] = None
    ) -> List[ValidationResult]:
        """
        Валидация результата расчетов

        Args:
            result: Результат из get_real_wb_data()
            reference_key: Ключ эталонных данных для сравнения

        Returns:
            Список результатов валидации
        """
        validation_results = []

        # 1. Проверка разумности сумм
        net_revenue = result.get('revenue', 0)
        gross_sales = result.get('gross_sales_value', 0)

        if reference_key and reference_key in self.reference_data:
            ref = self.reference_data[reference_key]
            expected_revenue = ref['expected_revenue']

            # Проверяем превышение
            if net_revenue > expected_revenue * 2:
                validation_results.append(ValidationResult(
                    rule_name="revenue_reasonableness",
                    passed=False,
                    actual_value=net_revenue / expected_revenue,
                    threshold=2.0,
                    severity="error",
                    message=f"Выручка {net_revenue:,.0f} ₽ превышает ожидаемую {expected_revenue:,.0f} ₽ более чем в 2 раза!"
                ))
            else:
                validation_results.append(ValidationResult(
                    rule_name="revenue_reasonableness",
                    passed=True,
                    actual_value=net_revenue / expected_revenue if expected_revenue > 0 else 0,
                    threshold=2.0,
                    severity="info",
                    message=f"Выручка {net_revenue:,.0f} ₽ в разумных пределах"
                ))

        # 2. Проверка дедупликации (из метаданных)
        if 'deduplication_stats' in result:
            stats = result['deduplication_stats']
            duplicates_percent = stats.get('duplicates_percent', 0)

            if duplicates_percent > 10.0:
                validation_results.append(ValidationResult(
                    rule_name="deduplication_quality",
                    passed=False,
                    actual_value=duplicates_percent,
                    threshold=10.0,
                    severity="warning",
                    message=f"Высокий процент дубликатов: {duplicates_percent:.1f}%"
                ))
            else:
                validation_results.append(ValidationResult(
                    rule_name="deduplication_quality",
                    passed=True,
                    actual_value=duplicates_percent,
                    threshold=10.0,
                    severity="info",
                    message=f"Дублирование в норме: {duplicates_percent:.1f}%"
                ))

        # 3. Проверка фильтрации дат
        if 'date_filtering_stats' in result:
            stats = result['date_filtering_stats']
            outside_percent = stats.get('records_outside_period_percent', 0)

            if outside_percent > 1.0:
                validation_results.append(ValidationResult(
                    rule_name="date_filtering_quality",
                    passed=False,
                    actual_value=outside_percent,
                    threshold=1.0,
                    severity="warning",
                    message=f"Много записей вне периода: {outside_percent:.1f}%"
                ))
            else:
                validation_results.append(ValidationResult(
                    rule_name="date_filtering_quality",
                    passed=True,
                    actual_value=outside_percent,
                    threshold=1.0,
                    severity="info",
                    message=f"Фильтрация дат корректна: {outside_percent:.1f}% вне периода"
                ))

        # 4. Проверка точности относительно эталона
        if reference_key and reference_key in self.reference_data:
            ref = self.reference_data[reference_key]
            expected_revenue = ref['expected_revenue']
            tolerance = ref['tolerance']

            deviation = abs(net_revenue - expected_revenue) / expected_revenue if expected_revenue > 0 else 0
            accuracy = (1 - deviation) * 100

            if accuracy < 95.0:
                validation_results.append(ValidationResult(
                    rule_name="accuracy_vs_reference",
                    passed=False,
                    actual_value=accuracy,
                    threshold=95.0,
                    severity="error",
                    message=f"Точность {accuracy:.1f}% ниже порога 95%. Отклонение: {deviation*100:.1f}%"
                ))
            else:
                validation_results.append(ValidationResult(
                    rule_name="accuracy_vs_reference",
                    passed=True,
                    actual_value=accuracy,
                    threshold=95.0,
                    severity="info",
                    message=f"Точность достигнута: {accuracy:.1f}%"
                ))

        # 5. Проверка forPay < priceWithDisc
        if gross_sales > 0:
            ratio = net_revenue / gross_sales

            if ratio >= 1.0:
                validation_results.append(ValidationResult(
                    rule_name="forpay_vs_pricewithdis",
                    passed=False,
                    actual_value=ratio,
                    threshold=1.0,
                    severity="error",
                    message=f"КРИТИЧЕСКАЯ ОШИБКА: forPay ({net_revenue:,.0f}) >= priceWithDisc ({gross_sales:,.0f})"
                ))
            elif ratio < 0.5:
                validation_results.append(ValidationResult(
                    rule_name="forpay_vs_pricewithdis",
                    passed=False,
                    actual_value=ratio,
                    threshold=0.5,
                    severity="warning",
                    message=f"Подозрительно низкий forPay ({ratio*100:.1f}% от priceWithDisc). Ожидается ~70-80%"
                ))
            else:
                validation_results.append(ValidationResult(
                    rule_name="forpay_vs_pricewithdis",
                    passed=True,
                    actual_value=ratio,
                    threshold=1.0,
                    severity="info",
                    message=f"Соотношение forPay/priceWithDisc корректно: {ratio*100:.1f}%"
                ))

        return validation_results

    def generate_alert_report(self, validation_results: List[ValidationResult]) -> str:
        """
        Генерация отчета с алертами

        Returns:
            Строка с отчетом
        """
        errors = [v for v in validation_results if v.severity == "error" and not v.passed]
        warnings = [v for v in validation_results if v.severity == "warning" and not v.passed]
        passed = [v for v in validation_results if v.passed]

        report = []
        report.append("\n" + "=" * 80)
        report.append("📊 ОТЧЕТ О ВАЛИДАЦИИ ДАННЫХ")
        report.append("=" * 80)
        report.append(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Проверок выполнено: {len(validation_results)}")
        report.append(f"Пройдено: {len(passed)}")
        report.append(f"Предупреждений: {len(warnings)}")
        report.append(f"Ошибок: {len(errors)}")
        report.append("=" * 80)

        if errors:
            report.append("\n❌ КРИТИЧЕСКИЕ ОШИБКИ:")
            for i, error in enumerate(errors, 1):
                report.append(f"{i}. {error.rule_name}: {error.message}")

        if warnings:
            report.append("\n⚠️ ПРЕДУПРЕЖДЕНИЯ:")
            for i, warning in enumerate(warnings, 1):
                report.append(f"{i}. {warning.rule_name}: {warning.message}")

        if passed:
            report.append("\n✅ ПРОЙДЕННЫЕ ПРОВЕРКИ:")
            for i, check in enumerate(passed, 1):
                report.append(f"{i}. {check.rule_name}: {check.message}")

        # Итоговый статус
        report.append("\n" + "=" * 80)
        if errors:
            report.append("🔴 СТАТУС: ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ ОШИБКИ")
        elif warnings:
            report.append("🟡 СТАТУС: ЕСТЬ ПРЕДУПРЕЖДЕНИЯ")
        else:
            report.append("🟢 СТАТУС: ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
        report.append("=" * 80 + "\n")

        return "\n".join(report)

    def log_validation_results(self, validation_results: List[ValidationResult]):
        """Логирование результатов валидации"""
        report = self.generate_alert_report(validation_results)
        logger.info(report)

        # Отдельные логи для критических ошибок
        errors = [v for v in validation_results if v.severity == "error" and not v.passed]
        for error in errors:
            logger.error(f"CRITICAL: {error.rule_name} - {error.message}")


# Пример использования
if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)

    # Создаем валидатор
    validator = DataValidator()

    # Пример результата для проверки
    test_result = {
        'revenue': 530000,  # forPay
        'gross_sales_value': 750000,  # priceWithDisc
        'wb_total_deductions': 220000,
        'units': 1234,
        'deduplication_stats': {
            'duplicates_removed': 5,
            'total_records': 1234,
            'duplicates_percent': 0.4
        },
        'date_filtering_stats': {
            'records_outside_period': 0,
            'total_records': 1234,
            'records_outside_period_percent': 0.0
        }
    }

    # Валидация
    results = validator.validate_result(test_result, reference_key='9_months_2025')

    # Вывод отчета
    validator.log_validation_results(results)
