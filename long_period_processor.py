#!/usr/bin/env python3
"""
Система обработки длительных периодов (год) с прогресс-баром в Telegram
Автоматическая разбивка больших периодов на допустимые чанки согласно лимитам API
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from aiogram import types

from real_data_reports import RealDataFinancialReports
from api_chunking import APIChunker

logger = logging.getLogger(__name__)


class LongPeriodProcessor:
    """Обработка длительных периодов с прогресс-индикацией"""

    def __init__(self):
        self.reports = RealDataFinancialReports()

    async def process_year_with_progress(
        self,
        date_from: str,
        date_to: str,
        progress_message: types.Message,
        max_delays: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Обработка данных за длительный период с обновлением прогресса в Telegram

        Args:
            date_from: Начальная дата (YYYY-MM-DD)
            date_to: Конечная дата (YYYY-MM-DD)
            progress_message: Сообщение Telegram для обновления прогресса
            max_delays: Максимальные задержки между запросами по типам API

        Returns:
            Агрегированные данные за весь период
        """
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            period_days = (end_date - start_date).days

            logger.info(f"🚀 Начинаем обработку БОЛЬШОГО периода: {period_days} дней ({date_from} - {date_to})")

            await self._update_progress(progress_message,
                f"🔄 Начинаю обработку данных за {period_days} дней\\n"
                f"📅 Период: {date_from} → {date_to}\\n\\n"
                f"⏳ Подготавливаю разбивку периода..."
            )

            # Определяем стратегию разбивки
            chunks_wb = APIChunker.chunk_date_range(date_from, date_to, 'wb_sales')
            chunks_ozon = APIChunker.chunk_date_range(date_from, date_to, 'ozon_fbo')

            total_chunks = len(chunks_wb) + len(chunks_ozon)

            await self._update_progress(progress_message,
                f"📊 План обработки:\\n"
                f"• WB данные: {len(chunks_wb)} периодов по ~90 дней\\n"
                f"• Ozon данные: {len(chunks_ozon)} периодов по ~30 дней\\n"
                f"• Всего периодов: {total_chunks}\\n\\n"
                f"🚀 Начинаем загрузку данных..."
            )

            # Обрабатываем WB данные по чанкам
            wb_aggregated = await self._process_wb_chunks(chunks_wb, progress_message, total_chunks)

            # Обрабатываем Ozon данные по чанкам
            ozon_aggregated = await self._process_ozon_chunks(chunks_ozon, progress_message, total_chunks, len(chunks_wb))

            # Финальная агрегация
            await self._update_progress(progress_message,
                f"🔄 Финальная обработка данных...\\n"
                f"✅ WB: {wb_aggregated.get('orders_stats', {}).get('count', 0)} заказов, {wb_aggregated.get('sales_stats', {}).get('count', 0)} продаж\\n"
                f"✅ Ozon: {ozon_aggregated.get('units', 0)} операций\\n\\n"
                f"⚡ Рассчитываю итоги..."
            )

            # Объединяем результаты
            final_result = self._aggregate_results(wb_aggregated, ozon_aggregated, date_from, date_to)

            await self._update_progress(progress_message,
                f"✅ Обработка завершена!\\n\\n"
                f"📊 **ИТОГИ за {period_days} дней:**\\n"
                f"💰 Общая выручка: {final_result.get('total_revenue', 0):,.0f} ₽\\n"
                f"📦 Всего единиц: {final_result.get('total_units', 0):,}\\n"
                f"🎯 Чистая прибыль: {final_result.get('net_profit', 0):,.0f} ₽\\n\\n"
                f"🚀 Генерирую финальный отчет..."
            )

            return final_result

        except Exception as e:
            logger.error(f"Ошибка обработки длительного периода: {e}")
            await self._update_progress(progress_message, f"❌ Ошибка: {str(e)[:100]}...")
            raise

    async def _process_wb_chunks(
        self,
        chunks: List[tuple],
        progress_message: types.Message,
        total_chunks: int
    ) -> Dict[str, Any]:
        """Обработка WB данных по чанкам с прогрессом"""

        wb_orders_all = []
        wb_sales_all = []
        processed = 0

        for i, (chunk_from, chunk_to) in enumerate(chunks, 1):
            try:
                await self._update_progress(progress_message,
                    f"🔄 WB данные {i}/{len(chunks)}\\n"
                    f"📅 Период: {chunk_from} → {chunk_to}\\n"
                    f"📊 Прогресс: {int(processed/total_chunks*100)}%\\n\\n"
                    f"⏳ Загружаю заказы и продажи..."
                )

                # Получаем данные за текущий чанк
                wb_data = await self.reports.get_real_wb_data(chunk_from, chunk_to)

                # Извлекаем детальную статистику
                orders_stats = wb_data.get('orders_stats', {})
                sales_stats = wb_data.get('sales_stats', {})

                # Логируем результат чанка
                logger.info(f"WB чанк {i}: заказов {orders_stats.get('count', 0)}, продаж {sales_stats.get('count', 0)}")

                # Сохраняем для агрегации
                if orders_stats.get('count', 0) > 0:
                    wb_orders_all.extend([orders_stats])
                if sales_stats.get('count', 0) > 0:
                    wb_sales_all.extend([sales_stats])

                processed += 1

                # Задержка между чанками для избежания rate limiting
                if i < len(chunks):
                    await asyncio.sleep(10.0)  # 10 секунд между большими периодами WB

            except Exception as e:
                logger.error(f"Ошибка в WB чанке {i} ({chunk_from}-{chunk_to}): {e}")
                processed += 1
                continue

        # Агрегируем WB данные
        return self._aggregate_wb_data(wb_orders_all, wb_sales_all)

    async def _process_ozon_chunks(
        self,
        chunks: List[tuple],
        progress_message: types.Message,
        total_chunks: int,
        wb_chunks_processed: int
    ) -> Dict[str, Any]:
        """Обработка Ozon данных по чанкам с прогрессом"""

        ozon_data_all = []
        processed = wb_chunks_processed

        for i, (chunk_from, chunk_to) in enumerate(chunks, 1):
            try:
                await self._update_progress(progress_message,
                    f"🔄 Ozon данные {i}/{len(chunks)}\\n"
                    f"📅 Период: {chunk_from} → {chunk_to}\\n"
                    f"📊 Общий прогресс: {int(processed/total_chunks*100)}%\\n\\n"
                    f"⏳ Загружаю транзакции..."
                )

                # Получаем данные за текущий чанк
                ozon_data = await self.reports.get_real_ozon_sales(chunk_from, chunk_to)

                logger.info(f"Ozon чанк {i}: единиц {ozon_data.get('units', 0)}, выручка {ozon_data.get('revenue', 0)}")

                # Сохраняем для агрегации
                if ozon_data.get('units', 0) > 0:
                    ozon_data_all.append(ozon_data)

                processed += 1

                # Задержка между чанками для избежания rate limiting
                if i < len(chunks):
                    await asyncio.sleep(5.0)  # 5 секунд между периодами Ozon

            except Exception as e:
                logger.error(f"Ошибка в Ozon чанке {i} ({chunk_from}-{chunk_to}): {e}")
                processed += 1
                continue

        # Агрегируем Ozon данные
        return self._aggregate_ozon_data(ozon_data_all)

    def _aggregate_wb_data(self, orders_list: List[Dict], sales_list: List[Dict]) -> Dict[str, Any]:
        """Агрегация WB данных"""
        total_orders_count = sum(o.get('count', 0) for o in orders_list)
        total_orders_revenue = sum(o.get('price_with_disc', 0) for o in orders_list)

        total_sales_count = sum(s.get('count', 0) for s in sales_list)
        total_sales_revenue = sum(s.get('for_pay', 0) for s in sales_list)

        return {
            'orders_stats': {
                'count': total_orders_count,
                'price_with_disc': total_orders_revenue
            },
            'sales_stats': {
                'count': total_sales_count,
                'for_pay': total_sales_revenue
            },
            'buyout_rate': (total_sales_count / total_orders_count * 100) if total_orders_count > 0 else 0
        }

    def _aggregate_ozon_data(self, ozon_list: List[Dict]) -> Dict[str, Any]:
        """Агрегация Ozon данных"""
        total_revenue = sum(data.get('revenue', 0) for data in ozon_list)
        total_units = sum(data.get('units', 0) for data in ozon_list)
        total_commission = sum(data.get('commission', 0) for data in ozon_list)

        return {
            'revenue': total_revenue,
            'units': total_units,
            'commission': total_commission
        }

    def _aggregate_results(self, wb_data: Dict, ozon_data: Dict, date_from: str, date_to: str) -> Dict[str, Any]:
        """Финальная агрегация всех результатов"""
        wb_revenue = wb_data.get('sales_stats', {}).get('for_pay', 0)
        ozon_revenue = ozon_data.get('revenue', 0)

        wb_units = wb_data.get('sales_stats', {}).get('count', 0)
        ozon_units = ozon_data.get('units', 0)

        total_revenue = wb_revenue + ozon_revenue
        total_units = wb_units + ozon_units

        # Примерный расчет чистой прибыли (нужно будет доработать)
        total_costs = total_revenue * 0.3  # Примерно 30% расходов
        net_profit = total_revenue - total_costs

        return {
            'period': f"{date_from} - {date_to}",
            'total_revenue': total_revenue,
            'total_units': total_units,
            'net_profit': net_profit,
            'wb_data': wb_data,
            'ozon_data': ozon_data
        }

    async def _update_progress(self, message: types.Message, text: str):
        """Обновление прогресса в Telegram"""
        try:
            await message.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка обновления прогресса: {e}")


# Глобальный экземпляр для использования в боте
long_processor = LongPeriodProcessor()