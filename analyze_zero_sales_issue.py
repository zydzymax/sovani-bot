#!/usr/bin/env python3
"""Анализ проблемы с нулевыми продажами на коротких периодах"""

import asyncio
import logging
from datetime import datetime, timedelta

import api_clients_main as api_clients
from api_chunking import ChunkedAPIManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ZeroSalesAnalyzer:
    """Анализатор проблемы с нулевыми продажами"""

    def __init__(self):
        self.chunked_manager = ChunkedAPIManager(api_clients)

    async def analyze_sales_timeline(self):
        """Анализ временной линии продаж"""
        logger.info("🔍 АНАЛИЗ ВРЕМЕННОЙ ЛИНИИ ПРОДАЖ")
        logger.info("=" * 50)

        # Тестируем разные периоды от сегодня назад
        today = datetime(2025, 9, 28)

        periods_to_test = [
            ("today", today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")),
            (
                "yesterday",
                (today - timedelta(days=1)).strftime("%Y-%m-%d"),
                (today - timedelta(days=1)).strftime("%Y-%m-%d"),
            ),
            (
                "2_days_ago",
                (today - timedelta(days=2)).strftime("%Y-%m-%d"),
                (today - timedelta(days=2)).strftime("%Y-%m-%d"),
            ),
            (
                "3_days_ago",
                (today - timedelta(days=3)).strftime("%Y-%m-%d"),
                (today - timedelta(days=3)).strftime("%Y-%m-%d"),
            ),
            (
                "last_week",
                (today - timedelta(days=7)).strftime("%Y-%m-%d"),
                (today - timedelta(days=7)).strftime("%Y-%m-%d"),
            ),
            ("september_start", "2025-09-01", "2025-09-07"),
            ("january_known_good", "2025-01-01", "2025-01-07"),
        ]

        results = {}

        for name, date_from, date_to in periods_to_test:
            logger.info(f"\n📅 Тестируем {name}: {date_from} - {date_to}")

            try:
                # Получаем Sales данные
                sales_data = await self.chunked_manager.get_wb_sales_chunked(date_from, date_to)
                sales_count = len(sales_data) if sales_data else 0

                # Получаем Orders данные
                orders_data = await self.chunked_manager.get_wb_orders_chunked(date_from, date_to)
                orders_count = len(orders_data) if orders_data else 0

                results[name] = {
                    "date_from": date_from,
                    "date_to": date_to,
                    "sales_count": sales_count,
                    "orders_count": orders_count,
                    "has_sales": sales_count > 0,
                    "has_orders": orders_count > 0,
                }

                status_sales = "✅" if sales_count > 0 else "❌"
                status_orders = "✅" if orders_count > 0 else "❌"

                logger.info(f"   {status_sales} Sales: {sales_count}")
                logger.info(f"   {status_orders} Orders: {orders_count}")

                # Анализ первых записей
                if sales_data and len(sales_data) > 0:
                    first_sale = sales_data[0]
                    logger.info(
                        f"   📊 Первая продажа: {first_sale.get('date', 'N/A')} - {first_sale.get('priceWithDisc', 0)}₽"
                    )

                if orders_data and len(orders_data) > 0:
                    first_order = orders_data[0]
                    logger.info(
                        f"   📊 Первый заказ: {first_order.get('date', 'N/A')} - {first_order.get('priceWithDisc', 0)}₽"
                    )

            except Exception as e:
                logger.error(f"   ❌ Ошибка: {e}")
                results[name] = {"date_from": date_from, "date_to": date_to, "error": str(e)}

            # Пауза между запросами
            await asyncio.sleep(2)

        return results

    def analyze_sales_lag_hypothesis(self, results):
        """Анализ гипотезы о лаге в продажах"""
        logger.info("\n🔍 АНАЛИЗ ГИПОТЕЗЫ О ЛАГЕ В ПРОДАЖАХ")
        logger.info("=" * 50)

        # Ищем паттерны в данных
        has_recent_sales = any(
            r.get("has_sales", False)
            for name, r in results.items()
            if "today" in name or "yesterday" in name
        )
        has_older_sales = any(
            r.get("has_sales", False)
            for name, r in results.items()
            if "ago" in name or "january" in name
        )

        logger.info(f"Продажи за последние дни: {'✅' if has_recent_sales else '❌'}")
        logger.info(f"Продажи за более старые периоды: {'✅' if has_older_sales else '❌'}")

        if not has_recent_sales and has_older_sales:
            logger.info("🎯 ГИПОТЕЗА: Sales API имеет лаг в несколько дней")
            logger.info("   Рекомендация: Использовать Orders для свежих данных")
        elif not has_recent_sales and not has_older_sales:
            logger.info("🎯 ГИПОТЕЗА: Проблема с Sales API или аккаунтом")
            logger.info("   Рекомендация: Проверить доступы к Sales API")
        else:
            logger.info("🎯 ДАННЫЕ ВЫГЛЯДЯТ НОРМАЛЬНО")

    async def get_sales_api_documentation(self):
        """Анализ документации Sales API"""
        logger.info("\n📚 АНАЛИЗ ОСОБЕННОСТЕЙ WB SALES API")
        logger.info("=" * 50)

        logger.info("🔍 ИЗВЕСТНЫЕ ОСОБЕННОСТИ WB SALES API:")
        logger.info("1. Sales API показывает ТОЛЬКО реализованные заказы")
        logger.info("2. Реализация происходит через 1-3 дня после заказа")
        logger.info("3. API может иметь задержку до 24 часов")
        logger.info("4. Данные появляются после подтверждения выкупа покупателем")

        logger.info("\n💡 ВОЗМОЖНЫЕ ПРИЧИНЫ НУЛЕВЫХ SALES:")
        logger.info("• Заказы еще не подтверждены покупателями")
        logger.info("• API задержка для свежих данных")
        logger.info("• Логистический лаг WB")
        logger.info("• Фильтр isRealization работает слишком строго")

        logger.info("\n🔧 РЕКОМЕНДАЦИИ:")
        logger.info("1. Для свежих данных (1-3 дня) использовать Orders API")
        logger.info("2. Для исторических данных (>3 дней) использовать Sales API")
        logger.info("3. Добавить гибридный подход: Orders + Sales")


async def main():
    """Основная функция анализа"""
    analyzer = ZeroSalesAnalyzer()

    logger.info("🚨 АНАЛИЗ ПРОБЛЕМЫ С НУЛЕВЫМИ ПРОДАЖАМИ")

    # Анализируем временную линию
    results = await analyzer.analyze_sales_timeline()

    # Анализируем гипотезу о лаге
    analyzer.analyze_sales_lag_hypothesis(results)

    # Получаем информацию о API
    await analyzer.get_sales_api_documentation()

    logger.info("\n🎉 АНАЛИЗ ЗАВЕРШЕН!")

    return results


if __name__ == "__main__":
    results = asyncio.run(main())
