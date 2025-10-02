#!/usr/bin/env python3
"""КОМПЛЕКСНАЯ СИСТЕМА ТЕСТИРОВАНИЯ И ВАЛИДАЦИИ
Проверка эффективности критических исправлений #1-3

Дата создания: 30 сентября 2025
Цель: Подтвердить точность данных после исправлений (дедупликация, фильтрация дат, унификация метрик)
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from real_data_reports import RealDataFinancialReports

import api_clients_main as api_clients
from api_chunking import ChunkedAPIManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f'/root/sovani_bot/validation_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Результат одного теста"""

    test_name: str
    period_start: str
    period_end: str
    period_days: int

    # Данные до обработки
    raw_records_count: int

    # Данные после дедупликации
    unique_records_count: int
    duplicates_removed: int
    deduplication_percent: float

    # Финансовые метрики
    net_revenue_to_seller: float  # forPay
    gross_sales_value: float  # priceWithDisc
    wb_total_deductions: float
    units_sold: int

    # Метрики качества
    records_outside_period: int
    date_parsing_errors: int

    # Эталонные данные (если есть)
    expected_revenue: float | None = None

    # Точность
    accuracy_percent: float | None = None

    # Статус теста
    test_passed: bool = False
    notes: str = ""


@dataclass
class ValidationReport:
    """Полный отчет о валидации"""

    report_date: str
    tests_total: int
    tests_passed: int
    tests_failed: int

    overall_accuracy: float
    deduplication_effectiveness: float
    date_filtering_quality: float

    test_results: list[TestResult]

    recommendations: list[str]
    summary: str


class ValidationTestSuite:
    """Комплексный набор тестов для валидации исправлений"""

    def __init__(self):
        self.reports = RealDataFinancialReports()
        self.chunked_api = ChunkedAPIManager(api_clients)

        # Эталонные данные из КРИТИЧЕСКОГО АУДИТА
        self.reference_data = {
            "january_2025": {
                "date_from": "2025-01-01",
                "date_to": "2025-01-31",
                "expected_orders_value": 113595,  # Из аудита
                "expected_sales_value": 60688,  # Из аудита
                "description": "Январь 2025 - эталонный период с известными значениями",
            }
        }

    async def test_1_day_period(self) -> TestResult:
        """ТЕСТ 1: Период 1 день
        Цель: Проверка базовой работоспособности без чанкинга
        """
        logger.info("=" * 80)
        logger.info("🧪 ТЕСТ 1: ПЕРИОД 1 ДЕНЬ")
        logger.info("=" * 80)

        date_to = datetime.now().strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        return await self._run_test(
            test_name="Тест 1: Период 1 день",
            date_from=date_from,
            date_to=date_to,
            expected_revenue=None,  # Нет эталона
        )

    async def test_7_days_period(self) -> TestResult:
        """ТЕСТ 2: Период 7 дней
        Цель: Проверка дедупликации на 1-2 чанках
        """
        logger.info("=" * 80)
        logger.info("🧪 ТЕСТ 2: ПЕРИОД 7 ДНЕЙ")
        logger.info("=" * 80)

        date_to = datetime.now().strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        return await self._run_test(
            test_name="Тест 2: Период 7 дней",
            date_from=date_from,
            date_to=date_to,
            expected_revenue=None,
        )

    async def test_30_days_period(self) -> TestResult:
        """ТЕСТ 3: Период 30 дней (1 месяц)
        Цель: Проверка дедупликации на 1-2 чанках
        """
        logger.info("=" * 80)
        logger.info("🧪 ТЕСТ 3: ПЕРИОД 30 ДНЕЙ")
        logger.info("=" * 80)

        date_to = datetime.now().strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        return await self._run_test(
            test_name="Тест 3: Период 30 дней",
            date_from=date_from,
            date_to=date_to,
            expected_revenue=None,
        )

    async def test_january_2025_reference(self) -> TestResult:
        """ТЕСТ 4: Январь 2025 (ЭТАЛОННЫЙ)
        Цель: Проверка на известных данных из аудита
        Ожидается: ~113,595₽ заказы, ~60,688₽ выкупы
        """
        logger.info("=" * 80)
        logger.info("🧪 ТЕСТ 4: ЯНВАРЬ 2025 (ЭТАЛОННЫЙ)")
        logger.info("=" * 80)

        ref = self.reference_data["january_2025"]

        logger.info("📋 Эталонные данные:")
        logger.info(f"   Ожидаемые заказы: {ref['expected_orders_value']:,.0f} ₽")
        logger.info(f"   Ожидаемые выкупы: {ref['expected_sales_value']:,.0f} ₽")

        return await self._run_test(
            test_name="Тест 4: Январь 2025 (эталонный)",
            date_from=ref["date_from"],
            date_to=ref["date_to"],
            expected_revenue=ref["expected_sales_value"],
        )

    async def _run_test(
        self, test_name: str, date_from: str, date_to: str, expected_revenue: float | None = None
    ) -> TestResult:
        """Выполнение одного теста

        Этапы:
        1. Получение сырых данных (с подсчетом)
        2. Проверка дедупликации
        3. Проверка фильтрации дат
        4. Расчет финансовых метрик
        5. Сравнение с эталоном (если есть)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔬 {test_name}")
        logger.info(f"📅 Период: {date_from} - {date_to}")
        logger.info(f"{'='*80}\n")

        period_days = (
            datetime.strptime(date_to, "%Y-%m-%d") - datetime.strptime(date_from, "%Y-%m-%d")
        ).days + 1

        try:
            # ШАГ 1: Получение сырых данных
            logger.info("📥 ШАГ 1: Получение сырых данных WB Sales...")

            # Получаем данные через исправленный API
            raw_sales = await self.chunked_api.get_wb_sales_chunked(date_from, date_to)
            raw_records_count = len(raw_sales) if raw_sales else 0

            logger.info(f"   Получено записей: {raw_records_count}")

            # ШАГ 2: Проверка дедупликации (уже встроена в ChunkedAPIManager)
            logger.info("\n🔍 ШАГ 2: Анализ дедупликации...")

            # Подсчет уникальных saleID
            unique_sale_ids = set()
            duplicates_in_raw = 0

            for sale in raw_sales:
                sale_id = sale.get("saleID")
                if sale_id:
                    if sale_id in unique_sale_ids:
                        duplicates_in_raw += 1
                    else:
                        unique_sale_ids.add(sale_id)

            unique_records_count = len(unique_sale_ids)
            duplicates_removed = duplicates_in_raw
            deduplication_percent = (
                (duplicates_removed / raw_records_count * 100) if raw_records_count > 0 else 0
            )

            logger.info(f"   Уникальных saleID: {unique_records_count}")
            logger.info(
                f"   Дубликатов найдено: {duplicates_removed} ({deduplication_percent:.1f}%)"
            )

            if duplicates_removed == 0:
                logger.info("   ✅ Дублирование отсутствует - дедупликация работает!")
            else:
                logger.warning(f"   ⚠️ Найдено {duplicates_removed} дубликатов - проверьте логику!")

            # ШАГ 3: Проверка фильтрации дат
            logger.info("\n📅 ШАГ 3: Проверка фильтрации дат...")

            records_outside_period = 0
            date_parsing_errors = 0

            from real_data_reports import is_date_in_range

            for sale in raw_sales:
                record_date = sale.get("date", "")
                if not record_date:
                    date_parsing_errors += 1
                    continue

                try:
                    if not is_date_in_range(record_date, date_from, date_to):
                        records_outside_period += 1
                except Exception:
                    date_parsing_errors += 1

            logger.info(f"   Записей вне периода: {records_outside_period}")
            logger.info(f"   Ошибок парсинга дат: {date_parsing_errors}")

            if records_outside_period == 0 and date_parsing_errors == 0:
                logger.info("   ✅ Фильтрация дат работает корректно!")
            else:
                logger.warning("   ⚠️ Обнаружены проблемы с фильтрацией дат")

            # ШАГ 4: Получение финансовых метрик через систему отчетов
            logger.info("\n💰 ШАГ 4: Расчет финансовых метрик...")

            result = await self.reports.get_real_wb_data(date_from, date_to)

            net_revenue_to_seller = result.get("revenue", 0)
            gross_sales_value = result.get("gross_sales_value", 0)
            wb_total_deductions = result.get("wb_total_deductions", 0)
            units_sold = result.get("units", 0)

            logger.info(f"   💵 Чистая выручка (forPay): {net_revenue_to_seller:,.2f} ₽")
            logger.info(f"   💰 Валовая стоимость (priceWithDisc): {gross_sales_value:,.2f} ₽")
            logger.info(f"   📉 Удержания WB: {wb_total_deductions:,.2f} ₽")
            logger.info(f"   📦 Единиц продано: {units_sold}")

            # ШАГ 5: Сравнение с эталоном
            accuracy_percent = None
            test_passed = False
            notes = []

            if expected_revenue is not None:
                logger.info("\n🎯 ШАГ 5: Сравнение с эталонными данными...")

                deviation = abs(net_revenue_to_seller - expected_revenue)
                accuracy_percent = (
                    100 - (deviation / expected_revenue * 100) if expected_revenue > 0 else 0
                )

                logger.info(f"   Ожидаемая выручка: {expected_revenue:,.2f} ₽")
                logger.info(f"   Фактическая выручка: {net_revenue_to_seller:,.2f} ₽")
                logger.info(f"   Отклонение: {deviation:,.2f} ₽ ({100 - accuracy_percent:.1f}%)")
                logger.info(f"   Точность: {accuracy_percent:.1f}%")

                # Критерий успеха: точность >= 95%
                if accuracy_percent >= 95.0:
                    test_passed = True
                    logger.info("   ✅ ТЕСТ ПРОЙДЕН: Точность >= 95%")
                else:
                    logger.warning(f"   ❌ ТЕСТ НЕ ПРОЙДЕН: Точность {accuracy_percent:.1f}% < 95%")
                    notes.append(f"Точность {accuracy_percent:.1f}% ниже порога 95%")
            else:
                logger.info("\n📊 ШАГ 5: Эталонные данные отсутствуют")
                logger.info("   Проверка только корректности обработки")

                # Базовые проверки
                if duplicates_removed == 0 and records_outside_period == 0:
                    test_passed = True
                    logger.info("   ✅ ТЕСТ ПРОЙДЕН: Дедупликация и фильтрация работают")
                else:
                    logger.warning("   ⚠️ Обнаружены проблемы в обработке данных")
                    if duplicates_removed > 0:
                        notes.append(f"Найдено {duplicates_removed} дубликатов")
                    if records_outside_period > 0:
                        notes.append(f"{records_outside_period} записей вне периода")

            # Формируем результат теста
            test_result = TestResult(
                test_name=test_name,
                period_start=date_from,
                period_end=date_to,
                period_days=period_days,
                raw_records_count=raw_records_count,
                unique_records_count=unique_records_count,
                duplicates_removed=duplicates_removed,
                deduplication_percent=deduplication_percent,
                net_revenue_to_seller=net_revenue_to_seller,
                gross_sales_value=gross_sales_value,
                wb_total_deductions=wb_total_deductions,
                units_sold=units_sold,
                records_outside_period=records_outside_period,
                date_parsing_errors=date_parsing_errors,
                expected_revenue=expected_revenue,
                accuracy_percent=accuracy_percent,
                test_passed=test_passed,
                notes="; ".join(notes) if notes else "OK",
            )

            logger.info(f"\n{'='*80}")
            logger.info(f"📊 РЕЗУЛЬТАТ ТЕСТА: {'✅ ПРОЙДЕН' if test_passed else '❌ НЕ ПРОЙДЕН'}")
            logger.info(f"{'='*80}\n")

            return test_result

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения теста: {e}", exc_info=True)

            return TestResult(
                test_name=test_name,
                period_start=date_from,
                period_end=date_to,
                period_days=period_days,
                raw_records_count=0,
                unique_records_count=0,
                duplicates_removed=0,
                deduplication_percent=0,
                net_revenue_to_seller=0,
                gross_sales_value=0,
                wb_total_deductions=0,
                units_sold=0,
                records_outside_period=0,
                date_parsing_errors=0,
                test_passed=False,
                notes=f"Ошибка: {e!s}",
            )

    async def run_all_tests(self) -> ValidationReport:
        """Запуск всех тестов и формирование итогового отчета"""
        logger.info("\n" + "=" * 80)
        logger.info("🚀 ЗАПУСК КОМПЛЕКСНОГО НАБОРА ТЕСТОВ")
        logger.info("=" * 80)
        logger.info(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("Цель: Валидация критических исправлений #1-3")
        logger.info("=" * 80 + "\n")

        test_results = []

        # Запуск всех тестов
        test_results.append(await self.test_1_day_period())
        test_results.append(await self.test_7_days_period())
        test_results.append(await self.test_30_days_period())
        test_results.append(await self.test_january_2025_reference())

        # Подсчет итогов
        tests_total = len(test_results)
        tests_passed = sum(1 for t in test_results if t.test_passed)
        tests_failed = tests_total - tests_passed

        # Общие метрики
        total_duplicates = sum(t.duplicates_removed for t in test_results)
        total_records = sum(t.raw_records_count for t in test_results)
        deduplication_effectiveness = (
            (total_duplicates / total_records * 100) if total_records > 0 else 0
        )

        total_outside_period = sum(t.records_outside_period for t in test_results)
        date_filtering_quality = (
            100 - (total_outside_period / total_records * 100) if total_records > 0 else 100
        )

        # Общая точность (только для тестов с эталоном)
        accuracy_tests = [t for t in test_results if t.accuracy_percent is not None]
        overall_accuracy = (
            sum(t.accuracy_percent for t in accuracy_tests) / len(accuracy_tests)
            if accuracy_tests
            else 0
        )

        # Рекомендации
        recommendations = []

        if deduplication_effectiveness > 5:
            recommendations.append(
                f"⚠️ Высокий процент дубликатов ({deduplication_effectiveness:.1f}%). "
                "Рекомендуется проверить логику chunking."
            )
        elif deduplication_effectiveness == 0:
            recommendations.append("✅ Дублирование отсутствует. Дедупликация работает идеально!")

        if date_filtering_quality < 99:
            recommendations.append(
                f"⚠️ Найдены записи вне периода ({100 - date_filtering_quality:.1f}%). "
                "Рекомендуется улучшить фильтрацию дат."
            )
        else:
            recommendations.append("✅ Фильтрация дат работает корректно!")

        if overall_accuracy >= 95:
            recommendations.append(
                f"✅ Целевая точность достигнута: {overall_accuracy:.1f}% >= 95%"
            )
        elif overall_accuracy > 0:
            recommendations.append(
                f"⚠️ Точность {overall_accuracy:.1f}% ниже целевой 95%. "
                "Требуется дополнительная диагностика."
            )

        # Итоговый summary
        summary = f"""
ИТОГОВЫЙ ОТЧЕТ О ВАЛИДАЦИИ:

Тестов выполнено: {tests_total}
Тестов пройдено: {tests_passed} ({tests_passed/tests_total*100:.0f}%)
Тестов не пройдено: {tests_failed}

ЭФФЕКТИВНОСТЬ ИСПРАВЛЕНИЙ:
- Дедупликация: {100 - deduplication_effectiveness:.1f}% (удалено {deduplication_effectiveness:.1f}% дубликатов)
- Фильтрация дат: {date_filtering_quality:.1f}%
- Общая точность: {overall_accuracy:.1f}%

СТАТУС: {'✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if tests_failed == 0 else '⚠️ ЕСТЬ ПРОБЛЕМЫ'}
"""

        # Формирование отчета
        report = ValidationReport(
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            tests_total=tests_total,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            overall_accuracy=overall_accuracy,
            deduplication_effectiveness=100 - deduplication_effectiveness,
            date_filtering_quality=date_filtering_quality,
            test_results=test_results,
            recommendations=recommendations,
            summary=summary,
        )

        # Вывод итогового отчета
        logger.info("\n" + "=" * 80)
        logger.info("📊 ИТОГОВЫЙ ОТЧЕТ О ВАЛИДАЦИИ")
        logger.info("=" * 80)
        logger.info(summary)

        logger.info("\n📋 РЕКОМЕНДАЦИИ:")
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"{i}. {rec}")

        logger.info("\n" + "=" * 80)

        return report

    def save_report(self, report: ValidationReport, filepath: str = None):
        """Сохранение отчета в JSON"""
        if filepath is None:
            filepath = f'/root/sovani_bot/validation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

        # Конвертация в dict
        report_dict = asdict(report)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"\n💾 Отчет сохранен: {filepath}")

        return filepath


async def main():
    """Главная функция - запуск всех тестов"""
    suite = ValidationTestSuite()

    # Запуск всех тестов
    report = await suite.run_all_tests()

    # Сохранение отчета
    report_path = suite.save_report(report)

    logger.info("\n✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    logger.info(f"📊 Отчет: {report_path}")

    return report


if __name__ == "__main__":
    report = asyncio.run(main())
