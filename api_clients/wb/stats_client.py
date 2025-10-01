"""Wildberries Statistics API Client
Клиент для работы с API статистики и продаж Wildberries
"""

import asyncio
import logging
import os
import sys
from datetime import date
from typing import Any

import aiohttp

# Добавляем путь к корневой директории проекта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import Config

logger = logging.getLogger(__name__)


class WBStatsClient:
    """Клиент для работы с API статистики Wildberries"""

    BASE_URL = "https://statistics-api.wildberries.ru"

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {Config.WB_STATS_TOKEN}",
            "Content-Type": "application/json",
        }
        logger.info("WBStatsClient инициализирован")

    async def sales(
        self, date_from: date, date_to: date, limit: int = 100000
    ) -> list[dict[str, Any]]:
        """Получение данных о продажах за период

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            limit: Лимит записей (максимум 100000)

        Returns:
            Список продаж с полями: date, lastChangeDate, warehouseName, countryName,
            oblastOkrugName, regionName, supplierArticle, nmId, barcode, category,
            subject, brand, techSize, incomeID, isSupply, isRealization, totalPrice,
            discountPercent, spp, finishedPrice, priceWithDisc, isStorno, orderType,
            sticker, gNumber, srid, forPay

        """
        try:
            url = f"{self.BASE_URL}/api/v1/supplier/sales"
            params = {
                "dateFrom": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d"),
                "limit": limit,
            }

            logger.info(f"Запрос продаж WB с {date_from} по {date_to}")

            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        sales_data = await response.json()
                        logger.info(f"WB API: получено {len(sales_data)} продаж")
                        return sales_data

                    elif response.status == 401:
                        logger.error("WB Stats API: Неверный токен авторизации")
                        logger.error(f"Используемый токен: {self.headers['Authorization'][:50]}...")
                        raise Exception("Неверный токен авторизации WB Stats API")

                    elif response.status == 429:
                        logger.warning("WB Stats API: Превышен лимит запросов, ожидаем...")
                        await asyncio.sleep(60)  # Ждем минуту
                        # Повторный запрос
                        async with session.get(
                            url, headers=self.headers, params=params
                        ) as retry_response:
                            if retry_response.status == 200:
                                retry_data = await retry_response.json()
                                logger.info(f"WB API (retry): получено {len(retry_data)} продаж")
                                return retry_data
                            else:
                                logger.error(f"WB Stats API retry failed: {retry_response.status}")
                                raise Exception(
                                    f"WB Stats API ошибка после retry: {retry_response.status}"
                                )

                    else:
                        logger.error(
                            f"WB Stats API ошибка {response.status}: {response_text[:500]}..."
                        )
                        raise Exception(f"WB Stats API ошибка: {response.status}")

        except Exception as e:
            logger.error(f"Критическая ошибка WB Stats API: {e}")
            raise

    async def orders(
        self, date_from: date, date_to: date, limit: int = 100000
    ) -> list[dict[str, Any]]:
        """Получение данных о заказах за период

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            limit: Лимит записей

        Returns:
            Список заказов

        """
        try:
            url = f"{self.BASE_URL}/api/v1/supplier/orders"
            params = {
                "dateFrom": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d"),
                "limit": limit,
            }

            logger.info(f"Запрос заказов WB с {date_from} по {date_to}")

            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        orders_data = await response.json()
                        logger.info(f"WB API: получено {len(orders_data)} заказов")
                        return orders_data

                    elif response.status == 401:
                        logger.error("WB Stats API Orders: Неверный токен авторизации")
                        raise Exception("Неверный токен авторизации WB Stats API")

                    else:
                        response_text = await response.text()
                        logger.error(
                            f"WB Orders API ошибка {response.status}: {response_text[:500]}"
                        )
                        raise Exception(f"WB Orders API ошибка: {response.status}")

        except Exception as e:
            logger.error(f"Критическая ошибка WB Orders API: {e}")
            raise

    async def stocks(self, date_from: date) -> list[dict[str, Any]]:
        """Получение данных об остатках на указанную дату

        Args:
            date_from: Дата для получения остатков

        Returns:
            Список остатков товаров

        """
        try:
            url = f"{self.BASE_URL}/api/v1/supplier/stocks"
            params = {"dateFrom": date_from.strftime("%Y-%m-%d")}

            logger.info(f"Запрос остатков WB на {date_from}")

            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        stocks_data = await response.json()
                        logger.info(f"WB API: получено {len(stocks_data)} позиций остатков")
                        return stocks_data

                    elif response.status == 401:
                        logger.error("WB Stats API Stocks: Неверный токен авторизации")
                        raise Exception("Неверный токен авторизации WB Stats API")

                    else:
                        response_text = await response.text()
                        logger.error(
                            f"WB Stocks API ошибка {response.status}: {response_text[:500]}"
                        )
                        raise Exception(f"WB Stocks API ошибка: {response.status}")

        except Exception as e:
            logger.error(f"Критическая ошибка WB Stocks API: {e}")
            raise

    async def report_detail_by_period(
        self, date_from: date, date_to: date, limit: int = 100000
    ) -> list[dict[str, Any]]:
        """Получение детализированного отчета за период
        Включает продажи, возвраты, отмены и другие операции

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            limit: Лимит записей

        Returns:
            Детализированный отчет

        """
        try:
            url = f"{self.BASE_URL}/api/v5/supplier/reportDetailByPeriod"
            params = {
                "dateFrom": date_from.strftime("%Y-%m-%d"),
                "dateTo": date_to.strftime("%Y-%m-%d"),
                "limit": limit,
            }

            logger.info(f"Запрос детализированного отчета WB с {date_from} по {date_to}")

            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        report_data = await response.json()
                        logger.info(
                            f"WB API: получено {len(report_data)} записей детализированного отчета"
                        )
                        return report_data

                    elif response.status == 401:
                        logger.error("WB Stats API Report: Неверный токен авторизации")
                        raise Exception("Неверный токен авторизации WB Stats API")

                    else:
                        response_text = await response.text()
                        logger.error(
                            f"WB Report API ошибка {response.status}: {response_text[:500]}"
                        )
                        raise Exception(f"WB Report API ошибка: {response.status}")

        except Exception as e:
            logger.error(f"Критическая ошибка WB Report API: {e}")
            raise


if __name__ == "__main__":
    """Тестирование клиента"""
    import asyncio

    async def test_wb_stats():
        client = WBStatsClient()

        # Тестируем получение продаж за последнюю неделю
        from datetime import timedelta

        date_to = date.today()
        date_from = date_to - timedelta(days=7)

        try:
            sales = await client.sales(date_from, date_to)
            print(f"Получено {len(sales)} продаж за период {date_from} - {date_to}")

            if sales:
                print("Пример записи продажи:")
                print(sales[0])

                total_revenue = sum(sale.get("forPay", 0) for sale in sales)
                print(f"Общая выручка: {total_revenue:.2f} ₽")
            else:
                print("Продаж за период не найдено")

        except Exception as e:
            print(f"Ошибка при тестировании: {e}")

    asyncio.run(test_wb_stats())
