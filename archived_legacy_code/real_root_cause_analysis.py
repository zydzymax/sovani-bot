#!/usr/bin/env python3
"""ЧЕСТНЫЙ АНАЛИЗ КОРНЕВЫХ ПРИЧИН
Поиск РЕАЛЬНЫХ причин завышения данных без подгонки коэффициентов
"""

import asyncio
import logging

import api_clients_main as api_clients
from api_chunking import ChunkedAPIManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RealRootCauseAnalyzer:
    """Анализатор реальных корневых причин без подгонки"""

    def __init__(self):
        self.chunked_manager = ChunkedAPIManager(api_clients)

    async def investigate_single_api_call(self):
        """Исследование одного API вызова для понимания РЕАЛЬНОЙ структуры данных"""
        logger.info("🔍 ИССЛЕДОВАНИЕ СЫРОГО API ОТВЕТА")
        logger.info("=" * 50)

        # Берем один день из января для детального анализа
        date_from = "2025-01-15"
        date_to = "2025-01-15"

        logger.info(f"📅 Анализируем: {date_from}")

        try:
            # Получаем сырые Sales данные
            logger.info("\n📊 СЫРЫЕ SALES ДАННЫЕ:")
            sales_data = await self.chunked_manager.get_wb_sales_chunked(date_from, date_to)

            if sales_data:
                logger.info(f"Получено записей: {len(sales_data)}")

                # Анализируем первые 3 записи детально
                for i, sale in enumerate(sales_data[:3]):
                    logger.info(f"\n🔸 Запись {i+1}:")
                    logger.info(f"  saleID: {sale.get('saleID', 'НЕТ')}")
                    logger.info(f"  date: {sale.get('date', 'НЕТ')}")
                    logger.info(f"  nmId: {sale.get('nmId', 'НЕТ')}")
                    logger.info(f"  subject: {sale.get('subject', 'НЕТ')}")
                    logger.info(f"  brand: {sale.get('brand', 'НЕТ')}")
                    logger.info(f"  supplierArticle: {sale.get('supplierArticle', 'НЕТ')}")
                    logger.info(f"  priceWithDisc: {sale.get('priceWithDisc', 0)}")
                    logger.info(f"  forPay: {sale.get('forPay', 0)}")
                    logger.info(f"  totalPrice: {sale.get('totalPrice', 0)}")
                    logger.info(f"  isRealization: {sale.get('isRealization', 'НЕТ')}")

                # Группировка по товарам
                products = {}
                for sale in sales_data:
                    nm_id = sale.get("nmId")
                    if nm_id:
                        if nm_id not in products:
                            products[nm_id] = []
                        products[nm_id].append(sale)

                logger.info("\n📦 АНАЛИЗ ПО ТОВАРАМ:")
                logger.info(f"Уникальных товаров: {len(products)}")

                for nm_id, sales in list(products.items())[:3]:
                    logger.info(f"\n🏷️ Товар {nm_id}:")
                    logger.info(f"  Продаж: {len(sales)}")
                    total_price = sum(s.get("priceWithDisc", 0) for s in sales)
                    logger.info(f"  Общая сумма: {total_price:,.0f} ₽")
                    avg_price = total_price / len(sales) if sales else 0
                    logger.info(f"  Средняя цена: {avg_price:,.0f} ₽")

            else:
                logger.warning("Нет Sales данных")

            # Получаем сырые Orders данные
            logger.info("\n📊 СЫРЫЕ ORDERS ДАННЫЕ:")
            orders_data = await self.chunked_manager.get_wb_orders_chunked(date_from, date_to)

            if orders_data:
                logger.info(f"Получено записей: {len(orders_data)}")

                # Анализируем первые 3 записи
                for i, order in enumerate(orders_data[:3]):
                    logger.info(f"\n🔸 Заказ {i+1}:")
                    logger.info(f"  date: {order.get('date', 'НЕТ')}")
                    logger.info(f"  nmId: {order.get('nmId', 'НЕТ')}")
                    logger.info(f"  subject: {order.get('subject', 'НЕТ')}")
                    logger.info(f"  brand: {order.get('brand', 'НЕТ')}")
                    logger.info(f"  supplierArticle: {order.get('supplierArticle', 'НЕТ')}")
                    logger.info(f"  priceWithDisc: {order.get('priceWithDisc', 0)}")
                    logger.info(f"  totalPrice: {order.get('totalPrice', 0)}")

            return {
                "sales_count": len(sales_data) if sales_data else 0,
                "orders_count": len(orders_data) if orders_data else 0,
                "sales_sample": sales_data[:3] if sales_data else [],
                "orders_sample": orders_data[:3] if orders_data else [],
            }

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return None

    def analyze_real_business_logic(self):
        """Анализ того, что РЕАЛЬНО означают API данные"""
        logger.info("\n🤔 АНАЛИЗ РЕАЛЬНОЙ БИЗНЕС-ЛОГИКИ")
        logger.info("=" * 50)

        logger.info("❓ ВОПРОСЫ ДЛЯ ПОНИМАНИЯ:")
        logger.info("1. В каких единицах цены в API? (рубли/копейки)")
        logger.info("2. Что означает priceWithDisc? (цена со скидкой)")
        logger.info("3. Что означает forPay? (к доплате/к перечислению)")
        logger.info("4. Что означает totalPrice? (полная цена без скидки)")
        logger.info("5. Когда появляются записи в Sales API?")
        logger.info("6. Может ли одна продажа генерить несколько записей?")

        logger.info("\n💡 ГИПОТЕЗЫ О ЗАВЫШЕНИИ:")
        logger.info("🔸 Гипотеза 1: Цены в копейках, а мы считаем в рублях")
        logger.info("🔸 Гипотеза 2: API возвращает дубликаты")
        logger.info("🔸 Гипотеза 3: Разные типы операций (продажи + возвраты)")
        logger.info("🔸 Гипотеза 4: Неправильное понимание полей API")
        logger.info("🔸 Гипотеза 5: Агрегация по неправильному полю")

    async def compare_with_wb_cabinet_data(self):
        """Сравнение с данными из личного кабинета WB"""
        logger.info("\n📱 СРАВНЕНИЕ С ЛИЧНЫМ КАБИНЕТОМ WB")
        logger.info("=" * 50)

        logger.info("📋 ЧТО НУЖНО ПРОВЕРИТЬ В КАБИНЕТЕ WB:")
        logger.info("1. Зайти в 'Аналитика' → 'Продажи'")
        logger.info("2. Выбрать период 15 января 2025")
        logger.info("3. Посмотреть:")
        logger.info("   - Количество проданных товаров")
        logger.info("   - Выручка с учетом скидок")
        logger.info("   - К перечислению")
        logger.info("   - Детализацию по товарам")

        logger.info("\n❗ ВАЖНО СРАВНИТЬ:")
        logger.info("- API priceWithDisc vs Кабинет 'Выручка со скидкой'")
        logger.info("- API forPay vs Кабинет 'К перечислению'")
        logger.info("- API количество vs Кабинет 'Продано штук'")

        logger.info("\n🎯 ЦЕЛЬ:")
        logger.info("Найти ТОЧНОЕ соответствие между API и кабинетом")
        logger.info("Понять откуда берется завышение в 10 раз")


async def main():
    """Основная функция честного анализа"""
    analyzer = RealRootCauseAnalyzer()

    logger.info("🚨 ЧЕСТНЫЙ АНАЛИЗ КОРНЕВЫХ ПРИЧИН")
    logger.info("БЕЗ ПОДГОНКИ КОЭФФИЦИЕНТОВ!")

    # Исследуем сырые API данные
    api_data = await analyzer.investigate_single_api_call()

    # Анализируем бизнес-логику
    analyzer.analyze_real_business_logic()

    # Даем рекомендации по сравнению с кабинетом
    await analyzer.compare_with_wb_cabinet_data()

    logger.info("\n🎯 ВЫВОДЫ:")
    logger.info("1. Нужно СРАВНИТЬ API данные с кабинетом WB")
    logger.info("2. Найти ТОЧНУЮ причину завышения")
    logger.info("3. НЕ использовать подгоночные коэффициенты")
    logger.info("4. Исправить КОРНЕВУЮ ПРИЧИНУ")

    return api_data


if __name__ == "__main__":
    result = asyncio.run(main())
