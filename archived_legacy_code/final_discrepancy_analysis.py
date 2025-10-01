#!/usr/bin/env python3
"""Финальный анализ расхождений на основе корректировок пользователя
Анализ причин завышения данных в 10 раз
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


class FinalDiscrepancyAnalyzer:
    """Финальный анализатор расхождений с корректировками пользователя"""

    def __init__(self):
        self.real_reports = RealDataFinancialReports()

    async def analyze_system_vs_reality(self):
        """Анализ системных данных против реальности"""
        logger.info("🎯 ФИНАЛЬНЫЙ АНАЛИЗ: СИСТЕМА vs РЕАЛЬНОСТЬ")
        logger.info("=" * 60)

        # Данные системы для января 2025
        date_from = "2025-01-01"
        date_to = "2025-01-31"

        logger.info(f"📅 Анализируемый период: {date_from} - {date_to}")

        try:
            # Получаем системные данные
            logger.info("\n🔍 ПОЛУЧЕНИЕ СИСТЕМНЫХ ДАННЫХ:")
            wb_data = await self.real_reports.get_real_wb_data(date_from, date_to)

            system_revenue = wb_data.get("revenue", 0)
            system_units = wb_data.get("units", 0)
            system_commission = wb_data.get("commission", 0)
            system_profit = wb_data.get("profit", 0)

            orders_stats = wb_data.get("orders_stats", {})
            sales_stats = wb_data.get("sales_stats", {})

            logger.info("   💻 Система показывает:")
            logger.info(f"      💰 Выручка: {system_revenue:,.0f} ₽")
            logger.info(f"      📦 Единиц: {system_units:,.0f} шт")
            logger.info(f"      🛒 Заказов: {orders_stats.get('count', 0):,.0f}")
            logger.info(f"      ✅ Продаж: {sales_stats.get('count', 0):,.0f}")
            logger.info(f"      💳 Комиссия: {system_commission:,.0f} ₽")
            logger.info(f"      💲 Прибыль: {system_profit:,.0f} ₽")

            # Реальные данные от пользователя
            logger.info("\n👤 РЕАЛЬНЫЕ ДАННЫЕ ОТ ПОЛЬЗОВАТЕЛЯ:")
            real_orders_amount = 113595  # Заказано на
            real_delivered_amount = 60688  # Выкуплено на

            logger.info(f"   📋 Заказано на: {real_orders_amount:,.0f} ₽")
            logger.info(f"   ✅ Выкуплено на: {real_delivered_amount:,.0f} ₽")

            # Расчет расхождений
            logger.info("\n📊 АНАЛИЗ РАСХОЖДЕНИЙ:")

            # Сравнение с заказами
            orders_system = orders_stats.get("price_with_disc", 0)
            orders_ratio = orders_system / real_orders_amount if real_orders_amount > 0 else 0
            orders_diff = orders_system - real_orders_amount

            logger.info("   🛒 ЗАКАЗЫ:")
            logger.info(f"      Система: {orders_system:,.0f} ₽")
            logger.info(f"      Реальность: {real_orders_amount:,.0f} ₽")
            logger.info(f"      Соотношение: {orders_ratio:.1f}x")
            logger.info(f"      Расхождение: {orders_diff:,.0f} ₽")

            # Сравнение с продажами
            sales_system = sales_stats.get("price_with_disc", 0)
            sales_ratio = sales_system / real_delivered_amount if real_delivered_amount > 0 else 0
            sales_diff = sales_system - real_delivered_amount

            logger.info("   ✅ ПРОДАЖИ/ВЫКУПЫ:")
            logger.info(f"      Система: {sales_system:,.0f} ₽")
            logger.info(f"      Реальность: {real_delivered_amount:,.0f} ₽")
            logger.info(f"      Соотношение: {sales_ratio:.1f}x")
            logger.info(f"      Расхождение: {sales_diff:,.0f} ₽")

            # Анализ причин расхождений
            logger.info("\n🤔 ВОЗМОЖНЫЕ ПРИЧИНЫ РАСХОЖДЕНИЙ:")

            logger.info("1️⃣ ПРОБЛЕМЫ С API ДАННЫМИ:")
            logger.info("   • Дублирование записей в API ответах")
            logger.info("   • Неправильная агрегация по периодам")
            logger.info("   • Включение отмененных/возвращенных заказов")
            logger.info("   • Ошибки в фильтрации isRealization")

            logger.info("\n2️⃣ ВАЛЮТНЫЕ/ЦЕНОВЫЕ ПРОБЛЕМЫ:")
            logger.info("   • Неправильная валюта (копейки вместо рублей)")
            logger.info("   • Включение НДС/налогов")
            logger.info("   • Разные типы цен (оптовые vs розничные)")

            logger.info("\n3️⃣ ВРЕМЕННЫЕ ПРОБЛЕМЫ:")
            logger.info("   • Неправильные временные зоны")
            logger.info("   • Пересечение периодов")
            logger.info("   • Учет переносов дат")

            logger.info("\n4️⃣ БИЗНЕС-ЛОГИКА:")
            logger.info("   • Разные определения 'выручки'")
            logger.info("   • Включение партнерских продаж")
            logger.info("   • Учет возвратов и отмен")

            # Рекомендации по исправлению
            logger.info("\n💡 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ:")

            logger.info("1️⃣ НЕМЕДЛЕННЫЕ ДЕЙСТВИЯ:")
            logger.info("   ✅ Проверить API ответы на дублирование")
            logger.info("   ✅ Добавить логирование сырых API данных")
            logger.info("   ✅ Проверить валюту в API ответах")
            logger.info("   ✅ Сравнить с данными из личного кабинета WB")

            logger.info("\n2️⃣ ТЕХНИЧЕСКИЕ ИСПРАВЛЕНИЯ:")
            logger.info("   🔧 Добавить дедупликацию записей")
            logger.info("   🔧 Пересмотреть логику агрегации")
            logger.info("   🔧 Улучшить фильтрацию данных")
            logger.info("   🔧 Добавить валидацию результатов")

            logger.info("\n3️⃣ КОНТРОЛЬ КАЧЕСТВА:")
            logger.info("   📋 Создать эталонные тесты")
            logger.info("   📋 Добавить проверки разумности данных")
            logger.info("   📋 Сравнение с историческими данными")
            logger.info("   📋 Ручная верификация случайных выборок")

            # Коэффициенты корректировки
            correction_factor_orders = (
                real_orders_amount / orders_system if orders_system > 0 else 0
            )
            correction_factor_sales = (
                real_delivered_amount / sales_system if sales_system > 0 else 0
            )

            logger.info("\n⚙️ КОЭФФИЦИЕНТЫ КОРРЕКТИРОВКИ:")
            logger.info(f"   🛒 Для заказов: {correction_factor_orders:.4f}")
            logger.info(f"   ✅ Для продаж: {correction_factor_sales:.4f}")

            # Пересчет годовых данных
            logger.info("\n📈 ПЕРЕСЧЕТ ГОДОВЫХ ПРОГНОЗОВ:")

            corrected_annual_orders = real_orders_amount * 9  # 9 месяцев
            corrected_annual_sales = real_delivered_amount * 9

            logger.info(
                f"   🛒 Скорректированный прогноз заказов: {corrected_annual_orders:,.0f} ₽"
            )
            logger.info(f"   ✅ Скорректированный прогноз продаж: {corrected_annual_sales:,.0f} ₽")
            logger.info("   🎯 Ожидания пользователя: 530,000 ₽")
            logger.info(f"   📊 Новое соотношение продаж: {corrected_annual_sales/530000:.1f}x")

            return {
                "system_data": {
                    "revenue": system_revenue,
                    "units": system_units,
                    "orders_amount": orders_system,
                    "sales_amount": sales_system,
                },
                "real_data": {
                    "orders_amount": real_orders_amount,
                    "delivered_amount": real_delivered_amount,
                },
                "discrepancies": {
                    "orders_ratio": orders_ratio,
                    "sales_ratio": sales_ratio,
                    "orders_diff": orders_diff,
                    "sales_diff": sales_diff,
                },
                "correction_factors": {
                    "orders": correction_factor_orders,
                    "sales": correction_factor_sales,
                },
                "corrected_projections": {
                    "annual_orders": corrected_annual_orders,
                    "annual_sales": corrected_annual_sales,
                    "vs_expectations": corrected_annual_sales / 530000,
                },
            }

        except Exception as e:
            logger.error(f"❌ Ошибка финального анализа: {e}")
            return None

    def create_configuration_recommendations(self, analysis_result):
        """Создание рекомендаций по настройке системы"""
        logger.info("\n⚙️ РЕКОМЕНДАЦИИ ПО НАСТРОЙКЕ СИСТЕМЫ:")
        logger.info("=" * 50)

        config_recommendations = {
            "immediate_fixes": {
                "data_validation": [
                    "Добавить проверку разумности сумм (макс. лимиты)",
                    "Валидация валюты в API ответах",
                    "Проверка на дублирование записей",
                    "Сравнение с предыдущими периодами",
                ],
                "api_improvements": [
                    "Логирование сырых API ответов",
                    "Дедупликация по уникальным ID",
                    "Улучшенная обработка ошибок API",
                    "Retry логика для сбоев",
                ],
            },
            "methodology_changes": {
                "calculation_method": "Использовать реальные выкупы (Sales API + isRealization)",
                "price_field": "priceWithDisc (цена со скидками)",
                "aggregation": "Сумма без дублирования",
                "validation": "Сравнение с эталонными данными",
            },
            "monitoring": {
                "alerts": [
                    "Превышение ожидаемых сумм более чем в 2 раза",
                    "Нулевые или отрицательные значения",
                    "Аномальные изменения между периодами",
                ],
                "reports": [
                    "Ежедневный контроль качества данных",
                    "Сравнение с данными из личного кабинета",
                    "Трендовый анализ",
                ],
            },
        }

        for category, items in config_recommendations.items():
            logger.info(f"\n🔧 {category.upper().replace('_', ' ')}:")
            if isinstance(items, dict):
                for key, value in items.items():
                    if isinstance(value, list):
                        logger.info(f"   {key}:")
                        for item in value:
                            logger.info(f"      • {item}")
                    else:
                        logger.info(f"   {key}: {value}")
            else:
                for item in items:
                    logger.info(f"   • {item}")

        return config_recommendations

    def save_final_report(self, analysis_result, config_recommendations):
        """Сохранение финального отчета"""
        final_report = {
            "report_date": datetime.now().isoformat(),
            "analysis_type": "final_discrepancy_analysis",
            "period_analyzed": "2025-01-01 to 2025-01-31",
            "key_findings": {
                "system_overcounting": "Система завышает данные в 9-10 раз",
                "primary_issue": "Проблема в источнике или обработке API данных",
                "correction_needed": "Требуется кардинальное исправление методики",
            },
            "analysis_result": analysis_result,
            "configuration_recommendations": config_recommendations,
            "next_steps": [
                "Исследовать сырые API ответы от WB",
                "Проверить дедупликацию данных",
                "Сравнить с данными из личного кабинета",
                "Внедрить коэффициенты корректировки",
                "Добавить контроль качества данных",
            ],
        }

        filename = f"final_discrepancy_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"/root/sovani_bot/reports/{filename}"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(final_report, f, ensure_ascii=False, indent=2)

            logger.info(f"\n💾 ФИНАЛЬНЫЙ ОТЧЕТ СОХРАНЕН: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения финального отчета: {e}")
            return None


async def main():
    """Основная функция финального анализа"""
    analyzer = FinalDiscrepancyAnalyzer()

    logger.info("🎯 ЗАПУСК ФИНАЛЬНОГО АНАЛИЗА РАСХОЖДЕНИЙ")

    # Проводим анализ системы против реальности
    analysis_result = await analyzer.analyze_system_vs_reality()

    if analysis_result:
        # Создаем рекомендации по настройке
        config_recommendations = analyzer.create_configuration_recommendations(analysis_result)

        # Сохраняем финальный отчет
        report_path = analyzer.save_final_report(analysis_result, config_recommendations)

        logger.info("\n🎉 ФИНАЛЬНЫЙ АНАЛИЗ ЗАВЕРШЕН!")
        logger.info("📋 Основная проблема: система завышает данные в 9-10 раз")
        logger.info("🔧 Требуется техническое исправление API обработки")
        logger.info(f"📄 Детальный отчет: {report_path}")

        return analysis_result, config_recommendations
    else:
        logger.error("❌ Финальный анализ не завершен из-за ошибок")
        return None, None


if __name__ == "__main__":
    result, config = asyncio.run(main())
