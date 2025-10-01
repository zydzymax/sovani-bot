#!/usr/bin/env python3
"""Система параллельной обработки API запросов
Максимально ускоряет получение данных за счет параллелизации
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ParallelDataProcessor:
    """Параллельный процессор данных WB и Ozon"""

    def __init__(self, real_data_reports):
        self.real_data_reports = real_data_reports

    async def get_parallel_financial_data(
        self, date_from: str, date_to: str, platform_filter: str = "both"
    ) -> dict[str, Any]:
        """МАКСИМАЛЬНО БЫСТРОЕ получение всех финансовых данных в параллель

        Args:
            date_from: Начальная дата YYYY-MM-DD
            date_to: Конечная дата YYYY-MM-DD
            platform_filter: "wb", "ozon", или "both" (по умолчанию)

        Returns:
            Dict с данными WB, Ozon и расходами

        """
        start_time = time.time()
        logger.info(
            f"🚀 ЗАПУСК ПАРАЛЛЕЛЬНОЙ ОБРАБОТКИ за {date_from} - {date_to}, платформы: {platform_filter}"
        )

        try:
            # СОЗДАЕМ ЗАДАЧИ НА ОСНОВЕ ФИЛЬТРА ПЛАТФОРМ
            tasks = []
            task_names = []

            if platform_filter in ["wb", "both"]:
                wb_task = asyncio.create_task(
                    self.real_data_reports.get_real_wb_data(date_from, date_to)
                )
                tasks.append(wb_task)
                task_names.append("wb")

            if platform_filter in ["ozon", "both"]:
                ozon_task = asyncio.create_task(
                    self.real_data_reports.get_real_ozon_sales(date_from, date_to)
                )
                tasks.append(ozon_task)
                task_names.append("ozon")

            # Запускаем подготовку расходов параллельно
            expenses_task = asyncio.create_task(self._prepare_expenses_data())
            tasks.append(expenses_task)
            task_names.append("expenses")

            # Ждем завершения всех задач
            logger.info(f"⏳ Ожидаем завершения задач: {', '.join(task_names)}")

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Распределяем результаты по платформам
            wb_data = {"revenue": 0, "units": 0, "cogs": 0, "commission": 0, "profit": 0}
            ozon_data = {"revenue": 0, "units": 0, "cogs": 0, "commission": 0, "profit": 0}
            expenses_data = {"opex": 0, "expenses_count": 0, "expenses_detail": []}

            result_index = 0
            if platform_filter in ["wb", "both"]:
                wb_data = (
                    results[result_index]
                    if not isinstance(results[result_index], Exception)
                    else wb_data
                )
                if isinstance(results[result_index], Exception):
                    logger.error(f"Ошибка WB данных: {results[result_index]}")
                result_index += 1

            if platform_filter in ["ozon", "both"]:
                ozon_data = (
                    results[result_index]
                    if not isinstance(results[result_index], Exception)
                    else ozon_data
                )
                if isinstance(results[result_index], Exception):
                    logger.error(f"Ошибка Ozon данных: {results[result_index]}")
                result_index += 1

            expenses_data = (
                results[result_index]
                if not isinstance(results[result_index], Exception)
                else expenses_data
            )
            if isinstance(results[result_index], Exception):
                logger.error(f"Ошибка расходов: {results[result_index]}")

            # Данные уже обработаны выше

            elapsed = time.time() - start_time
            logger.info(f"✅ ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА ЗАВЕРШЕНА за {elapsed:.1f}с")

            return {
                "wb": wb_data,
                "ozon": ozon_data,
                "expenses": expenses_data,
                "processing_time": elapsed,
                "parallelized": True,
                "platform_filter": platform_filter,
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Критическая ошибка параллельной обработки: {e}")

            # Fallback к последовательной обработке
            logger.info("🔄 Переключение на последовательную обработку...")
            return await self._fallback_sequential_processing(
                date_from, date_to, elapsed, platform_filter
            )

    async def _prepare_expenses_data(self) -> dict[str, Any]:
        """Подготовка данных о расходах (быстрая операция)"""
        try:
            # Получаем расходы с тестовыми данными
            revenue_data = {"wb": 0, "ozon": 0, "total": 0}  # Будет обновлено позже
            units_sold = {"wb": 0, "ozon": 0, "total": 0}
            orders_count = {"wb": 0, "ozon": 0, "total": 0}

            expenses_result = await self.real_data_reports.get_real_expenses(
                revenue_data, units_sold, orders_count
            )

            return expenses_result

        except Exception as e:
            logger.error(f"Ошибка подготовки расходов: {e}")
            return {"opex": 0, "expenses_count": 0, "expenses_detail": []}

    async def _fallback_sequential_processing(
        self, date_from: str, date_to: str, failed_time: float, platform_filter: str = "both"
    ) -> dict[str, Any]:
        """Резервная последовательная обработка"""
        start_time = time.time()

        try:
            # Инициализируем данные с нулевыми значениями
            wb_data = {"revenue": 0, "units": 0, "cogs": 0, "commission": 0, "profit": 0}
            ozon_data = {"revenue": 0, "units": 0, "cogs": 0, "commission": 0, "profit": 0}

            # Получаем данные только для выбранных платформ
            if platform_filter in ["wb", "both"]:
                wb_data = await self.real_data_reports.get_real_wb_data(date_from, date_to)

            if platform_filter in ["ozon", "both"]:
                ozon_data = await self.real_data_reports.get_real_ozon_sales(date_from, date_to)

            # Обновляем расходы с реальными данными
            revenue_data = {
                "wb": wb_data.get("revenue", 0),
                "ozon": ozon_data.get("revenue", 0),
                "total": wb_data.get("revenue", 0) + ozon_data.get("revenue", 0),
            }
            units_sold = {
                "wb": wb_data.get("units", 0),
                "ozon": ozon_data.get("units", 0),
                "total": wb_data.get("units", 0) + ozon_data.get("units", 0),
            }
            orders_count = {"wb": 0, "ozon": 0, "total": 0}

            expenses_data = await self.real_data_reports.get_real_expenses(
                revenue_data, units_sold, orders_count
            )

            elapsed = time.time() - start_time
            total_time = failed_time + elapsed

            logger.info(
                f"✅ Последовательная обработка завершена за {elapsed:.1f}с (общее время: {total_time:.1f}с)"
            )

            return {
                "wb": wb_data,
                "ozon": ozon_data,
                "expenses": expenses_data,
                "processing_time": total_time,
                "parallelized": False,
                "platform_filter": platform_filter,
            }

        except Exception as e:
            logger.error(f"❌ Критическая ошибка последовательной обработки: {e}")
            return {
                "wb": {"revenue": 0, "units": 0, "cogs": 0, "commission": 0, "profit": 0},
                "ozon": {"revenue": 0, "units": 0, "cogs": 0, "commission": 0, "profit": 0},
                "expenses": {"opex": 0, "expenses_count": 0, "expenses_detail": []},
                "processing_time": time.time() - start_time + failed_time,
                "parallelized": False,
                "platform_filter": platform_filter,
                "error": str(e),
            }

    async def get_optimized_chunked_data(
        self, date_from: str, date_to: str, platform_filter: str = "both"
    ) -> dict[str, Any]:
        """ОПТИМИЗИРОВАННОЕ получение данных с chunking в параллель

        Особенно эффективно для больших периодов
        """
        start_time = time.time()

        # Определяем период и стратегию
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        period_days = (end_date - start_date).days

        logger.info(f"🔥 ОПТИМИЗИРОВАННАЯ ОБРАБОТКА {period_days} дней...")

        if period_days <= 7:
            # Для коротких периодов используем обычную параллелизацию
            return await self.get_parallel_financial_data(date_from, date_to, platform_filter)

        else:
            # Для длинных периодов используем chunked API в параллель
            return await self._parallel_chunked_processing(
                date_from, date_to, period_days, platform_filter
            )

    async def _parallel_chunked_processing(
        self, date_from: str, date_to: str, period_days: int, platform_filter: str = "both"
    ) -> dict[str, Any]:
        """Параллельная обработка с chunking для больших периодов"""
        start_time = time.time()

        logger.info(f"⚡ CHUNKED ПАРАЛЛЕЛИЗАЦИЯ для {period_days} дней")

        try:
            # Создаем задачи только для выбранных платформ
            tasks = []
            task_names = []

            if platform_filter in ["wb", "both"]:
                wb_chunked_task = asyncio.create_task(
                    self._get_wb_chunked_parallel(date_from, date_to)
                )
                tasks.append(wb_chunked_task)
                task_names.append("wb_chunked")

            if platform_filter in ["ozon", "both"]:
                ozon_chunked_task = asyncio.create_task(
                    self._get_ozon_chunked_parallel(date_from, date_to)
                )
                tasks.append(ozon_chunked_task)
                task_names.append("ozon_chunked")

            # Ждем завершения chunked обработки
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Распределяем результаты
            wb_chunked_data = []
            ozon_chunked_data = {"revenue": 0, "units": 0, "commission": 0, "profit": 0}

            result_index = 0
            if platform_filter in ["wb", "both"]:
                wb_chunked_data = (
                    results[result_index]
                    if not isinstance(results[result_index], Exception)
                    else []
                )
                if isinstance(results[result_index], Exception):
                    logger.error(f"Ошибка WB chunked: {results[result_index]}")
                result_index += 1

            if platform_filter in ["ozon", "both"]:
                ozon_chunked_data = (
                    results[result_index]
                    if not isinstance(results[result_index], Exception)
                    else {"revenue": 0, "units": 0, "commission": 0, "profit": 0}
                )
                if isinstance(results[result_index], Exception):
                    logger.error(f"Ошибка Ozon chunked: {results[result_index]}")

            # Данные уже обработаны выше

            # Агрегируем данные и рассчитываем финальные метрики
            wb_data = await self._aggregate_wb_chunked_data(wb_chunked_data, date_from, date_to)
            # ИСПРАВЛЕНИЕ: ozon_chunked_data уже готовый dict, агрегация не нужна
            ozon_data = ozon_chunked_data

            # Рассчитываем расходы
            revenue_data = {
                "wb": wb_data.get("revenue", 0),
                "ozon": ozon_data.get("revenue", 0),
                "total": wb_data.get("revenue", 0) + ozon_data.get("revenue", 0),
            }
            units_sold = {
                "wb": wb_data.get("units", 0),
                "ozon": ozon_data.get("units", 0),
                "total": wb_data.get("units", 0) + ozon_data.get("units", 0),
            }
            orders_count = {"wb": 0, "ozon": 0, "total": 0}

            expenses_data = await self.real_data_reports.get_real_expenses(
                revenue_data, units_sold, orders_count
            )

            elapsed = time.time() - start_time
            logger.info(f"🎯 CHUNKED ПАРАЛЛЕЛИЗАЦИЯ ЗАВЕРШЕНА за {elapsed:.1f}с")

            return {
                "wb": wb_data,
                "ozon": ozon_data,
                "expenses": expenses_data,
                "processing_time": elapsed,
                "parallelized": True,
                "chunked": True,
                "period_days": period_days,
                "platform_filter": platform_filter,
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Ошибка chunked параллелизации: {e}")
            return await self._fallback_sequential_processing(
                date_from, date_to, elapsed, platform_filter
            )

    async def _get_wb_chunked_parallel(self, date_from: str, date_to: str) -> list[dict]:
        """Получение WB данных через chunked API"""
        try:
            chunked_manager = self.real_data_reports.chunked_api

            # Запускаем sales и orders параллельно
            sales_task = asyncio.create_task(
                chunked_manager.get_wb_sales_chunked(date_from, date_to)
            )
            orders_task = asyncio.create_task(
                chunked_manager.get_wb_orders_chunked(date_from, date_to)
            )

            sales_data, orders_data = await asyncio.gather(
                sales_task, orders_task, return_exceptions=True
            )

            return {
                "sales": sales_data if not isinstance(sales_data, Exception) else [],
                "orders": orders_data if not isinstance(orders_data, Exception) else [],
            }

        except Exception as e:
            logger.error(f"Ошибка WB chunked параллель: {e}")
            return {"sales": [], "orders": []}

    async def _get_ozon_chunked_parallel(self, date_from: str, date_to: str) -> dict[str, Any]:
        """Получение Ozon данных через правильный метод"""
        try:
            # ИСПРАВЛЕНИЕ: Используем get_real_ozon_sales вместо get_ozon_fbs_chunked
            return await self.real_data_reports.get_real_ozon_sales(date_from, date_to)
        except Exception as e:
            logger.error(f"Ошибка Ozon получения: {e}")
            return {"revenue": 0, "units": 0, "commission": 0, "profit": 0}

    async def _aggregate_wb_chunked_data(
        self, chunked_data: dict, date_from: str, date_to: str
    ) -> dict[str, Any]:
        """Агрегация WB chunked данных"""
        try:
            sales_data = chunked_data.get("sales", [])
            orders_data = chunked_data.get("orders", [])

            # Используем логику из real_data_reports для расчета метрик
            total_revenue = sum(
                sale.get("forPay", 0) for sale in sales_data if sale.get("isRealization")
            )
            total_units = len([sale for sale in sales_data if sale.get("isRealization")])
            total_commission = sum(
                sale.get("totalPrice", 0) - sale.get("forPay", 0)
                for sale in sales_data
                if sale.get("isRealization")
            )

            return {
                "revenue": total_revenue,
                "units": total_units,
                "commission": total_commission,
                "cogs": 0,  # Рассчитается отдельно
                "profit": total_revenue - total_commission,
                "sales_data": sales_data,
                "orders_data": orders_data,
            }

        except Exception as e:
            logger.error(f"Ошибка агрегации WB: {e}")
            return {"revenue": 0, "units": 0, "commission": 0, "cogs": 0, "profit": 0}

    async def _aggregate_ozon_chunked_data(
        self, chunked_data: list[dict], date_from: str, date_to: str
    ) -> dict[str, Any]:
        """Агрегация Ozon chunked данных"""
        try:
            total_revenue = 0
            total_units = 0
            total_commission = 0

            for transaction in chunked_data:
                if transaction.get("operation_type") == "OperationMarketplace":
                    accruals = transaction.get("accruals_for_sale", 0)
                    total_revenue += accruals
                    total_units += 1

                elif (
                    transaction.get("operation_type")
                    == "OperationMarketplaceServicePremiumCashback"
                ):
                    commission_fee = abs(transaction.get("accruals_for_sale", 0))
                    total_commission += commission_fee

            return {
                "revenue": total_revenue,
                "units": total_units,
                "commission": total_commission,
                "cogs": 0,
                "profit": total_revenue - total_commission,
                "transactions": chunked_data,
            }

        except Exception as e:
            logger.error(f"Ошибка агрегации Ozon: {e}")
            return {"revenue": 0, "units": 0, "commission": 0, "cogs": 0, "profit": 0}


# Глобальный экземпляр для использования
_parallel_processor = None


def get_parallel_processor(real_data_reports):
    """Получение глобального экземпляра параллельного процессора"""
    global _parallel_processor
    if _parallel_processor is None:
        _parallel_processor = ParallelDataProcessor(real_data_reports)
    return _parallel_processor
