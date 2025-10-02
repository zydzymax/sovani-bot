#!/usr/bin/env python3
"""ЭКСТРЕННАЯ ДИАГНОСТИКА ПЕРИОДОВ
Пошаговое тестирование коротких, средних и длинных периодов
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

from emergency_data_correction import CorrectedFinancialReports
from real_data_reports import RealDataFinancialReports

import api_clients_main as api_clients
from api_chunking import ChunkedAPIManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PeriodDiagnosticSystem:
    """Система диагностики разных периодов"""

    def __init__(self):
        self.original_reports = RealDataFinancialReports()
        self.corrected_reports = CorrectedFinancialReports()
        self.chunked_manager = ChunkedAPIManager(api_clients)

        # Результаты тестирования
        self.test_results = {}

    def get_test_periods(self) -> list[tuple[str, str, str, int]]:
        """Получение тестовых периодов"""
        # Базовая дата - сегодня
        today = datetime(2025, 9, 28)  # Текущая дата

        periods = [
            # (name, date_from, date_to, days)
            (
                "1_day",
                (today - timedelta(days=1)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
                1,
            ),
            (
                "7_days",
                (today - timedelta(days=7)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
                7,
            ),
            (
                "14_days",
                (today - timedelta(days=14)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
                14,
            ),
            (
                "30_days",
                (today - timedelta(days=30)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
                30,
            ),
            (
                "60_days",
                (today - timedelta(days=60)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
                60,
            ),
            (
                "90_days",
                (today - timedelta(days=90)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
                90,
            ),
        ]

        return periods

    async def test_single_period(self, name: str, date_from: str, date_to: str, days: int) -> dict:
        """Тестирование одного периода"""
        logger.info(f"\n🔍 ТЕСТИРОВАНИЕ ПЕРИОДА: {name}")
        logger.info("=" * 50)
        logger.info(f"📅 Период: {date_from} - {date_to} ({days} дней)")

        test_result = {
            "name": name,
            "date_from": date_from,
            "date_to": date_to,
            "days": days,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "original_data": None,
            "corrected_data": None,
            "chunking_info": None,
            "api_calls": 0,
            "errors": [],
        }

        try:
            # 1. Анализ chunking стратегии
            chunking_info = await self.analyze_chunking_strategy(date_from, date_to)
            test_result["chunking_info"] = chunking_info

            # 2. Получение оригинальных данных
            logger.info("📥 Получение оригинальных данных...")
            try:
                original_data = await self.original_reports.get_real_wb_data(date_from, date_to)
                test_result["original_data"] = original_data
                logger.info(
                    f"   ✅ Оригинальные данные получены: {original_data.get('revenue', 0):,.0f} ₽"
                )
            except Exception as e:
                error_msg = f"Ошибка получения оригинальных данных: {e}"
                test_result["errors"].append(error_msg)
                logger.error(f"   ❌ {error_msg}")

            # 3. Получение исправленных данных
            logger.info("🔧 Получение исправленных данных...")
            try:
                corrected_data = await self.corrected_reports.get_corrected_wb_data(
                    date_from, date_to
                )
                test_result["corrected_data"] = corrected_data
                logger.info(
                    f"   ✅ Исправленные данные получены: {corrected_data.get('revenue', 0):,.0f} ₽"
                )
            except Exception as e:
                error_msg = f"Ошибка получения исправленных данных: {e}"
                test_result["errors"].append(error_msg)
                logger.error(f"   ❌ {error_msg}")

            # 4. Анализ результатов
            if original_data and corrected_data:
                analysis = self.analyze_period_results(original_data, corrected_data, days)
                test_result.update(analysis)
                test_result["success"] = True

                logger.info(f"\n📊 АНАЛИЗ РЕЗУЛЬТАТОВ ПЕРИОДА {name}:")
                logger.info(
                    f"   🔄 Соотношение оригинал/исправленный: {analysis.get('correction_ratio', 0):.2f}x"
                )
                logger.info(
                    f"   📈 Выручка в день (оригинал): {analysis.get('daily_revenue_original', 0):,.0f} ₽"
                )
                logger.info(
                    f"   📈 Выручка в день (исправленная): {analysis.get('daily_revenue_corrected', 0):,.0f} ₽"
                )

            return test_result

        except Exception as e:
            error_msg = f"Общая ошибка тестирования периода {name}: {e}"
            test_result["errors"].append(error_msg)
            logger.error(f"❌ {error_msg}")
            return test_result

    async def analyze_chunking_strategy(self, date_from: str, date_to: str) -> dict:
        """Анализ стратегии chunking для периода"""
        logger.info("🔍 Анализ chunking стратегии...")

        # Вычисляем количество дней
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        days_diff = (end_date - start_date).days

        # Определяем стратегию chunking (логика из api_chunking.py)
        if days_diff <= 30:
            strategy = "short_period"
            delay = 1.5
            expected_chunks = 1
        elif days_diff <= 90:
            strategy = "medium_period"
            delay = 2.0
            expected_chunks = max(1, days_diff // 45)
        else:
            strategy = "long_period"
            delay = 3.0
            expected_chunks = max(1, days_diff // 45)

        chunking_info = {
            "days": days_diff,
            "strategy": strategy,
            "delay_between_requests": delay,
            "expected_chunks": expected_chunks,
            "max_api_calls": expected_chunks * 2,  # Sales + Orders для каждого чанка
        }

        logger.info(f"   📊 Дней: {days_diff}")
        logger.info(f"   🔄 Стратегия: {strategy}")
        logger.info(f"   ⏱️ Задержка: {delay}s")
        logger.info(f"   📦 Ожидается чанков: {expected_chunks}")
        logger.info(f"   🌐 Макс. API вызовов: {chunking_info['max_api_calls']}")

        return chunking_info

    def analyze_period_results(self, original_data: dict, corrected_data: dict, days: int) -> dict:
        """Анализ результатов за период"""
        original_revenue = original_data.get("revenue", 0)
        corrected_revenue = corrected_data.get("revenue", 0)

        analysis = {
            "original_revenue": original_revenue,
            "corrected_revenue": corrected_revenue,
            "correction_ratio": (
                original_revenue / corrected_revenue if corrected_revenue > 0 else 0
            ),
            "daily_revenue_original": original_revenue / days if days > 0 else 0,
            "daily_revenue_corrected": corrected_revenue / days if days > 0 else 0,
            "revenue_difference": original_revenue - corrected_revenue,
            "revenue_difference_pct": (
                ((original_revenue - corrected_revenue) / corrected_revenue * 100)
                if corrected_revenue > 0
                else 0
            ),
        }

        return analysis

    async def run_progressive_testing(self) -> dict:
        """Запуск прогрессивного тестирования от коротких к длинным периодам"""
        logger.info("🚨 ЗАПУСК ПРОГРЕССИВНОГО ТЕСТИРОВАНИЯ ПЕРИОДОВ")
        logger.info("=" * 60)

        periods = self.get_test_periods()
        results = {}

        for name, date_from, date_to, days in periods:
            logger.info(f"\n{'='*20} ПЕРИОД {name.upper()} {'='*20}")

            # Тестируем период
            test_result = await self.test_single_period(name, date_from, date_to, days)
            results[name] = test_result

            # Анализируем результат
            if test_result["success"]:
                logger.info(f"✅ Период {name} протестирован успешно")

                # Проверяем качество данных
                if self.is_period_data_reliable(test_result):
                    logger.info(f"🎯 Данные за период {name} НАДЕЖНЫ")
                else:
                    logger.info(f"⚠️ Данные за период {name} НЕНАДЕЖНЫ - ОСТАНОВКА")
                    break
            else:
                logger.error(f"❌ Период {name} завершился с ошибками:")
                for error in test_result["errors"]:
                    logger.error(f"   • {error}")
                logger.error("🛑 ОСТАНОВКА ТЕСТИРОВАНИЯ")
                break

            # Задержка между тестами
            logger.info("⏱️ Пауза перед следующим тестом...")
            await asyncio.sleep(5)

        # Сохраняем результаты
        self.save_diagnostic_results(results)

        return results

    def is_period_data_reliable(self, test_result: dict) -> bool:
        """Проверка надежности данных за период"""
        if not test_result.get("success"):
            return False

        # Проверяем коэффициент коррекции
        correction_ratio = test_result.get("correction_ratio", 0)

        # Данные считаем надежными, если коррекция в разумных пределах (5-15x)
        if 5 <= correction_ratio <= 15:
            return True

        # Если коррекция слишком большая или маленькая - данные ненадежны
        return False

    def save_diagnostic_results(self, results: dict):
        """Сохранение результатов диагностики"""
        filename = f"period_diagnostic_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"/root/sovani_bot/reports/{filename}"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"\n💾 Результаты диагностики сохранены: {filepath}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения результатов: {e}")

    def print_summary(self, results: dict):
        """Печать итогового отчета"""
        logger.info("\n📋 ИТОГОВЫЙ ОТЧЕТ ДИАГНОСТИКИ ПЕРИОДОВ")
        logger.info("=" * 60)

        for period_name, result in results.items():
            if result.get("success"):
                status = "✅ УСПЕХ"
                revenue_orig = result.get("original_revenue", 0)
                revenue_corr = result.get("corrected_revenue", 0)
                ratio = result.get("correction_ratio", 0)

                logger.info(
                    f"{period_name:>10}: {status} | {revenue_orig:>10,.0f} → {revenue_corr:>8,.0f} ₽ ({ratio:.1f}x)"
                )
            else:
                status = "❌ ОШИБКА"
                logger.info(f"{period_name:>10}: {status}")


async def main():
    """Основная функция диагностики"""
    diagnostic = PeriodDiagnosticSystem()

    logger.info("🚨 СТАРТ ЭКСТРЕННОЙ ДИАГНОСТИКИ ПЕРИОДОВ")

    # Запускаем прогрессивное тестирование
    results = await diagnostic.run_progressive_testing()

    # Печатаем итоговый отчет
    diagnostic.print_summary(results)

    logger.info("\n🎉 ДИАГНОСТИКА ЗАВЕРШЕНА!")

    return results


if __name__ == "__main__":
    results = asyncio.run(main())
