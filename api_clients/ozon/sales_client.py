"""
Ozon Sales API Client
Клиент для работы с API продаж Ozon
"""

import aiohttp
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
import sys
import os

# Добавляем путь к корневой директории проекта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from config import Config

logger = logging.getLogger(__name__)


class OzonSalesClient:
    """Клиент для работы с API продаж Ozon"""

    BASE_URL = "https://api-seller.ozon.ru"

    def __init__(self):
        self.headers = {
            'Client-Id': Config.OZON_CLIENT_ID,
            'Api-Key': Config.OZON_API_KEY_ADMIN,
            'Content-Type': 'application/json'
        }
        logger.info(f"OzonSalesClient инициализирован с Client-Id: {Config.OZON_CLIENT_ID}")

    async def get_finance_transaction_totals(self, date_from: date, date_to: date) -> Dict[str, Any]:
        """
        Получение сводных данных по транзакциям через v3 API

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода

        Returns:
            Сводные данные по транзакциям
        """
        try:
            url = f"{self.BASE_URL}/v3/finance/transaction/totals"
            payload = {
                "date": {
                    "from": f"{date_from}T00:00:00.000Z",
                    "to": f"{date_to}T23:59:59.999Z"
                }
            }

            logger.info(f"Запрос сводных данных Ozon Transaction Totals с {date_from} по {date_to}")

            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        totals_data = await response.json()
                        result = totals_data.get('result', {})
                        logger.info(f"Ozon Transaction Totals API: получены сводные данные")
                        logger.info(f"  Начисления к доплате: {result.get('accruals_for_sale', 0)}")
                        logger.info(f"  Комиссия за продажу: {result.get('sale_commission', 0)}")
                        return totals_data

                    elif response.status == 401:
                        logger.error("Ozon Transaction Totals API: Неверные учетные данные")
                        raise Exception("Неверные учетные данные Ozon API")

                    elif response.status == 429:
                        logger.warning("Ozon Transaction Totals API: Превышен лимит запросов, ожидаем...")
                        await asyncio.sleep(60)
                        # Повторный запрос
                        async with session.post(url, headers=self.headers, json=payload) as retry_response:
                            if retry_response.status == 200:
                                retry_data = await retry_response.json()
                                logger.info(f"Ozon Transaction Totals API (retry): получены данные")
                                return retry_data
                            else:
                                logger.error(f"Ozon Transaction Totals API retry failed: {retry_response.status}")
                                raise Exception(f"Ozon Transaction Totals API ошибка после retry: {retry_response.status}")

                    else:
                        logger.error(f"Ozon Transaction Totals API ошибка {response.status}: {response_text[:500]}")
                        raise Exception(f"Ozon Transaction Totals API ошибка: {response.status}")

        except Exception as e:
            logger.error(f"Критическая ошибка Ozon Transaction Totals API: {e}")
            raise


    async def get_finance_realization(self, date_from: date, date_to: date) -> Dict[str, Any]:
        """
        Получение отчета о реализации (продажах) через v2 API

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода

        Returns:
            Отчет о реализации
        """
        try:
            # ИСПРАВЛЕНИЕ: используем v2 API с правильным форматом year/month
            # Получаем данные для каждого месяца в диапазоне
            all_data = {"result": {"rows": []}}

            current_date = date_from.replace(day=1)  # Начинаем с первого числа месяца
            end_date = date_to

            while current_date <= end_date:
                url = f"{self.BASE_URL}/v2/finance/realization"
                payload = {
                    "year": current_date.year,
                    "month": current_date.month
                }

                logger.info(f"Запрос отчета Ozon Realization v2 за {current_date.month:02d}.{current_date.year}")

                timeout = aiohttp.ClientTimeout(total=60, connect=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=self.headers, json=payload) as response:
                        response_text = await response.text()

                        if response.status == 200:
                            monthly_data = await response.json()
                            result = monthly_data.get('result', {})
                            rows = result.get('rows', [])
                            all_data["result"]["rows"].extend(rows)
                            logger.info(f"Ozon API v2: получено {len(rows)} записей за {current_date.month:02d}.{current_date.year}")

                        elif response.status == 404:
                            logger.warning(f"Ozon Realization v2: нет данных за {current_date.month:02d}.{current_date.year}")
                            # Продолжаем, возможно данные еще не готовы

                        elif response.status == 401:
                            logger.error("Ozon Realization API: Неверные учетные данные")
                            raise Exception("Неверные учетные данные Ozon API")

                        else:
                            logger.error(f"Ozon Realization API ошибка {response.status}: {response_text[:500]}")
                            # Не прерываем, пытаемся получить данные за другие месяцы

                # Переходим к следующему месяцу
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)

                await asyncio.sleep(1)  # Пауза между запросами

            total_rows = len(all_data["result"]["rows"])
            logger.info(f"Ozon Realization v2: всего получено {total_rows} записей за период")
            return all_data

        except Exception as e:
            logger.error(f"Критическая ошибка Ozon Realization API: {e}")
            raise

    async def get_analytics_data(self, date_from: date, date_to: date, metrics: List[str] = None) -> Dict[str, Any]:
        """
        Получение аналитических данных через Analytics API

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            metrics: Список метрик (по умолчанию: revenue, ordered_units)

        Returns:
            Аналитические данные
        """
        if metrics is None:
            metrics = ["revenue", "ordered_units", "hits_view_search", "hits_view_pdp", "conversion"]

        try:
            url = f"{self.BASE_URL}/v1/analytics/data"
            payload = {
                "date_from": date_from.strftime('%Y-%m-%d'),
                "date_to": date_to.strftime('%Y-%m-%d'),
                "metrics": metrics,
                "dimension": ["sku"],
                "filters": [],
                "sort": [],
                "limit": 1000,
                "offset": 0
            }

            logger.info(f"Запрос аналитики Ozon с {date_from} по {date_to}, метрики: {metrics}")

            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        analytics_data = await response.json()
                        result = analytics_data.get('result', {})
                        data_rows = result.get('data', [])
                        logger.info(f"Ozon Analytics API: получено {len(data_rows)} записей")
                        return analytics_data

                    elif response.status == 401:
                        logger.error("Ozon Analytics API: Неверные учетные данные")
                        raise Exception("Неверные учетные данные Ozon API")

                    else:
                        logger.error(f"Ozon Analytics API ошибка {response.status}: {response_text[:500]}")
                        raise Exception(f"Ozon Analytics API ошибка: {response.status}")

        except Exception as e:
            logger.error(f"Критическая ошибка Ozon Analytics API: {e}")
            raise

    async def calculate_revenue_from_transaction_totals(self, date_from: date, date_to: date) -> Dict[str, float]:
        """
        Подсчет выручки из сводных данных по транзакциям

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода

        Returns:
            Словарь с финансовыми показателями
        """
        try:
            totals_data = await self.get_finance_transaction_totals(date_from, date_to)
            result = totals_data.get('result', {})

            # Извлекаем основные финансовые показатели
            accruals_for_sale = float(result.get('accruals_for_sale', 0))
            sale_commission = float(result.get('sale_commission', 0))
            processing_and_delivery = float(result.get('processing_and_delivery', 0))
            refunds_and_cancellations = float(result.get('refunds_and_cancellations', 0))

            # Рассчитываем чистую выручку
            gross_revenue = accruals_for_sale
            net_revenue = gross_revenue - abs(sale_commission) - abs(refunds_and_cancellations)

            logger.info(f"Ozon Transaction Totals за период {date_from} - {date_to}:")
            logger.info(f"  Начисления к доплате: {accruals_for_sale:,.2f} ₽")
            logger.info(f"  Комиссия за продажу: {sale_commission:,.2f} ₽")
            logger.info(f"  Валовая выручка: {gross_revenue:,.2f} ₽")
            logger.info(f"  Чистая выручка: {net_revenue:,.2f} ₽")

            return {
                'gross_revenue': gross_revenue,
                'net_revenue': net_revenue,
                'commission': abs(sale_commission),
                'refunds': abs(refunds_and_cancellations)
            }

        except Exception as e:
            logger.error(f"Ошибка расчета выручки из Transaction Totals: {e}")
            raise


    async def calculate_revenue_from_realization(self, date_from: date, date_to: date) -> float:
        """
        Подсчет реальной выручки из отчета реализации

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода

        Returns:
            Общая выручка в рублях
        """
        try:
            realization_data = await self.get_finance_realization(date_from, date_to)

            rows = realization_data.get('result', {}).get('rows', [])
            total_revenue = 0.0
            sales_count = 0

            for row in rows:
                # В отчете реализации ищем реальные продажи
                operation_type = row.get('operation_type', '')
                amount = float(row.get('accruals_for_sale', 0))

                if operation_type == 'OperationMarketplaceSellerRevenue' and amount > 0:
                    total_revenue += amount
                    sales_count += 1
                    logger.debug(f"Найдена реализация: {operation_type}, сумма: {amount}")

            logger.info(f"Ozon Realization: найдено {sales_count} реализаций, общая выручка: {total_revenue:.2f} ₽")
            return total_revenue

        except Exception as e:
            logger.error(f"Ошибка подсчета выручки из отчета реализации: {e}")
            raise

    async def get_fbo_orders(self, date_from: date, date_to: date) -> Dict[str, Any]:
        """
        Получение заказов FBO (Fulfillment by Ozon) - содержит реальные данные о заказах

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода

        Returns:
            Данные о заказах FBO
        """
        try:
            url = f"{self.BASE_URL}/v2/posting/fbo/list"
            payload = {
                "dir": "ASC",
                "filter": {
                    "since": f"{date_from}T00:00:00.000Z",
                    "to": f"{date_to}T23:59:59.999Z"
                },
                "limit": 1000,
                "offset": 0,
                "with": {
                    "analytics_data": True
                }
            }

            logger.info(f"Запрос FBO заказов Ozon с {date_from} по {date_to}")

            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        fbo_data = await response.json()
                        logger.info(f"Ozon FBO: тип ответа = {type(fbo_data)}")

                        if isinstance(fbo_data, dict):
                            result = fbo_data.get('result', {})
                            if isinstance(result, dict):
                                postings = result.get('postings', [])
                                logger.info(f"Ozon FBO API: получено {len(postings)} заказов")
                            elif isinstance(result, list):
                                # ИСПРАВЛЕНИЕ: result может быть списком заказов
                                logger.info(f"Ozon FBO: result - список из {len(result)} заказов")
                                postings = result
                            else:
                                logger.warning(f"Ozon FBO: result не dict и не list, а {type(result)}")
                                postings = []
                        elif isinstance(fbo_data, list):
                            logger.warning(f"Ozon FBO: получен список из {len(fbo_data)} элементов")
                            postings = fbo_data
                        else:
                            logger.error(f"Ozon FBO: неожиданный тип {type(fbo_data)}")
                            postings = []

                        return fbo_data

                    elif response.status == 401:
                        logger.error("Ozon FBO API: Неверные учетные данные")
                        raise Exception("Неверные учетные данные Ozon API")

                    else:
                        logger.error(f"Ozon FBO API ошибка {response.status}: {response_text[:500]}")
                        raise Exception(f"Ozon FBO API ошибка: {response.status}")

        except Exception as e:
            logger.error(f"Критическая ошибка Ozon FBO API: {e}")
            raise

    async def calculate_revenue_from_fbo(self, date_from: date, date_to: date) -> float:
        """
        Подсчет реальной выручки из FBO заказов (только доставленные заказы)

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода

        Returns:
            Общая выручка в рублях из доставленных FBO заказов
        """
        try:
            fbo_data = await self.get_fbo_orders(date_from, date_to)

            postings = fbo_data.get('result', {}).get('postings', [])
            total_revenue = 0.0
            delivered_count = 0

            for posting in postings:
                status = posting.get('status', '')

                # Считаем только доставленные заказы
                if status == 'delivered':
                    # Суммируем стоимость всех товаров в заказе
                    products = posting.get('products', [])
                    order_revenue = 0.0

                    for product in products:
                        price = float(product.get('price', 0))
                        quantity = int(product.get('quantity', 0))
                        order_revenue += price * quantity

                    total_revenue += order_revenue
                    delivered_count += 1
                    logger.debug(f"Доставленный FBO заказ: {posting.get('posting_number')}, выручка: {order_revenue:.2f}")

            logger.info(f"Ozon FBO: найдено {delivered_count} доставленных заказов, общая выручка: {total_revenue:.2f} ₽")
            return total_revenue

        except Exception as e:
            logger.error(f"Ошибка подсчета выручки из FBO заказов: {e}")
            raise

    async def get_transactions(self, date_from: date, date_to: date) -> List[Dict]:
        """
        Получение всех транзакций через Transaction API

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода

        Returns:
            Список всех транзакций
        """
        all_transactions = []
        page = 1

        try:
            while page <= 10:  # Ограничиваем до 10 страниц
                payload = {
                    "filter": {
                        "date": {
                            "from": f"{date_from}T00:00:00.000Z",
                            "to": f"{date_to}T23:59:59.999Z"
                        }
                    },
                    "page": page,
                    "page_size": 1000
                }

                logger.info(f"Получаем транзакции Ozon, страница {page}")

                timeout = aiohttp.ClientTimeout(total=60, connect=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(f"{self.BASE_URL}/v3/finance/transaction/list",
                                          headers=self.headers, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            operations = data.get('result', {}).get('operations', [])

                            if not operations:
                                break

                            all_transactions.extend(operations)
                            logger.info(f"Страница {page}: получено {len(operations)} операций")
                            page += 1
                        else:
                            logger.error(f"Ошибка получения транзакций: {response.status}")
                            break

        except Exception as e:
            logger.error(f"Ошибка получения транзакций: {e}")

        logger.info(f"Всего получено транзакций: {len(all_transactions)}")
        return all_transactions

    async def calculate_revenue_from_transactions(self, date_from: date, date_to: date) -> Dict[str, float]:
        """
        Расчет выручки из транзакций с разделением на заказы и выкупы

        Returns:
            Словарь с данными о заказах и выкупах
        """
        transactions = await self.get_transactions(date_from, date_to)

        delivered_revenue = 0.0  # Выкупы (доставленные)
        delivered_count = 0

        for transaction in transactions:
            operation_type = transaction.get('operation_type', '')
            accruals = float(transaction.get('accruals_for_sale', 0))

            # Операции доставки клиенту = выкупы
            if operation_type == 'OperationAgentDeliveredToCustomer' and accruals > 0:
                delivered_revenue += accruals
                delivered_count += 1

        logger.info(f"Ozon транзакции за период {date_from} - {date_to}:")
        logger.info(f"  Доставленных операций: {delivered_count}")
        logger.info(f"  Выручка от выкупов: {delivered_revenue:.2f} ₽")

        return {
            'delivered_revenue': delivered_revenue,
            'delivered_count': delivered_count
        }

    async def get_revenue(self, date_from: date, date_to: date) -> Dict[str, float]:
        """
        Получение полных данных о выручке с разделением заказов и выкупов

        Returns:
            Словарь с полными данными о выручке
        """
        revenue_data = {}

        try:
            # Метод 1: Analytics API - все заказы
            analytics_data = await self.get_analytics_data(date_from, date_to, ['revenue', 'ordered_units'])
            analytics_revenue = 0.0
            analytics_units = 0.0

            for row in analytics_data.get('result', {}).get('data', []):
                metrics = row.get('metrics', [])
                if len(metrics) >= 2:
                    analytics_revenue += float(metrics[0] or 0)
                    analytics_units += float(metrics[1] or 0)

            revenue_data['total_orders_revenue'] = analytics_revenue
            revenue_data['total_orders_units'] = analytics_units

        except Exception as e:
            logger.warning(f"Не удалось получить данные Analytics: {e}")
            revenue_data['total_orders_revenue'] = 0.0
            revenue_data['total_orders_units'] = 0.0

        try:
            # Метод 2: Transaction API - только выкупы
            transaction_data = await self.calculate_revenue_from_transactions(date_from, date_to)
            revenue_data['delivered_revenue'] = transaction_data['delivered_revenue']
            revenue_data['delivered_count'] = transaction_data['delivered_count']

        except Exception as e:
            logger.warning(f"Не удалось получить транзакции: {e}")
            revenue_data['delivered_revenue'] = 0.0
            revenue_data['delivered_count'] = 0

        # Расчет процента выкупа
        if revenue_data['total_orders_revenue'] > 0:
            buyout_rate = (revenue_data['delivered_revenue'] / revenue_data['total_orders_revenue']) * 100
            revenue_data['buyout_rate'] = buyout_rate
        else:
            revenue_data['buyout_rate'] = 0.0

        # Основные показатели для совместимости
        revenue_data['best_estimate'] = revenue_data['delivered_revenue']  # Выкупы как основная метрика
        revenue_data['data_source'] = 'transactions'

        logger.info(f"Ozon полные данные за период {date_from} - {date_to}:")
        logger.info(f"  Все заказы: {revenue_data['total_orders_revenue']:.2f} ₽ ({revenue_data['total_orders_units']:.0f} ед.)")
        logger.info(f"  Выкупы: {revenue_data['delivered_revenue']:.2f} ₽ ({revenue_data['delivered_count']} операций)")
        logger.info(f"  Процент выкупа: {revenue_data['buyout_rate']:.1f}%")

        return revenue_data


if __name__ == "__main__":
    """Тестирование клиента"""
    import asyncio

    async def test_ozon_sales():
        client = OzonSalesClient()

        # Тестируем получение выручки за последнюю неделю
        from datetime import timedelta
        date_to = date.today()
        date_from = date_to - timedelta(days=7)

        try:
            revenue_data = await client.get_revenue(date_from, date_to)
            print(f"Результаты для периода {date_from} - {date_to}:")

            for method, amount in revenue_data.items():
                print(f"{method}: {amount:.2f} ₽")

        except Exception as e:
            print(f"Ошибка при тестировании: {e}")

    asyncio.run(test_ozon_sales())