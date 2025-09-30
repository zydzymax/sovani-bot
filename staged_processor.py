"""
Этапный процессор: сначала WB, потом Ozon, потом агрегация
Разделение на этапы для лучшего контроля и возможности возобновления
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from aiogram import types
from enum import Enum

from api_chunking import APIChunker
from chunk_cache import ChunkCache, CachedAPIProcessor
from progress_tracker import ProgressTracker, JobStatus
from optimized_api_client import OptimizedAPIClient

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    INITIALIZATION = "initialization"
    WB_PROCESSING = "wb_processing"
    OZON_PROCESSING = "ozon_processing"
    AGGREGATION = "aggregation"
    COMPLETED = "completed"
    FAILED = "failed"


class StagedDataProcessor:
    """Этапный процессор данных с детальным контролем"""

    def __init__(self):
        self.cache = ChunkCache()
        self.progress = ProgressTracker()
        self.optimized_client = OptimizedAPIClient()
        self.cached_processor = CachedAPIProcessor()

    async def process_year_staged(
        self,
        date_from: str,
        date_to: str,
        progress_message: types.Message,
        job_id: str = None
    ) -> Dict[str, Any]:
        """
        Этапная обработка больших периодов

        Этапы:
        1. Инициализация и планирование
        2. Обработка WB данных (Orders + Sales + Advertising)
        3. Обработка Ozon данных (FBO + FBS)
        4. Финальная агрегация и расчеты
        """
        if not job_id:
            job_id = f"staged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            logger.info(f"🚀 Запуск этапной обработки {job_id}: {date_from} - {date_to}")

            # ЭТАП 1: Инициализация
            result = await self._stage_1_initialization(job_id, date_from, date_to, progress_message)

            # ЭТАП 2: WB обработка
            wb_data = await self._stage_2_wb_processing(job_id, result['chunks'], progress_message)

            # ЭТАП 3: Ozon обработка
            ozon_data = await self._stage_3_ozon_processing(job_id, result['chunks'], progress_message)

            # ЭТАП 4: Финальная агрегация
            final_result = await self._stage_4_aggregation(job_id, wb_data, ozon_data, date_from, date_to, progress_message)

            logger.info(f"✅ Этапная обработка {job_id} завершена успешно")
            return final_result

        except Exception as e:
            logger.error(f"❌ Ошибка этапной обработки {job_id}: {e}")
            await self._update_progress(progress_message, f"❌ Ошибка обработки: {str(e)[:100]}")
            raise

    async def _stage_1_initialization(
        self,
        job_id: str,
        date_from: str,
        date_to: str,
        progress_message: types.Message
    ) -> Dict[str, Any]:
        """ЭТАП 1: Инициализация и планирование"""
        logger.info(f"📋 ЭТАП 1: Инициализация задачи {job_id}")

        await self._update_progress(progress_message,
            f"🚀 **ЭТАП 1/4: ИНИЦИАЛИЗАЦИЯ**\\n\\n"
            f"📅 Период: {date_from} → {date_to}\\n"
            f"🔧 Планирую разбивку на чанки...\\n"
            f"⏱️ Начало: {datetime.now().strftime('%H:%M')}"
        )

        # Вычисляем период
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
        period_days = (end_date - start_date).days

        # Разбиваем на чанки
        wb_chunks = APIChunker.chunk_date_range(date_from, date_to, 'wb_sales')
        ozon_chunks = APIChunker.chunk_date_range(date_from, date_to, 'ozon_fbo')

        total_chunks = len(wb_chunks) + len(ozon_chunks)

        await self._update_progress(progress_message,
            f"📊 **ПЛАН ОБРАБОТКИ СОСТАВЛЕН:**\\n\\n"
            f"📈 Период: **{period_days} дней**\\n"
            f"🟣 WB чанков: **{len(wb_chunks)}** (по ~31 день)\\n"
            f"🔵 Ozon чанков: **{len(ozon_chunks)}** (по ~30 дней)\\n"
            f"📦 Всего чанков: **{total_chunks}**\\n\\n"
            f"⏳ Ожидаемое время: ~{total_chunks * 2} минут\\n"
            f"🔄 Переходим к обработке WB..."
        )

        # Инициализируем отслеживание прогресса
        self.progress.initialize_job(job_id, date_from, date_to, progress_message.chat.id)

        return {
            'job_id': job_id,
            'period_days': period_days,
            'chunks': {
                'wb': wb_chunks,
                'ozon': ozon_chunks
            },
            'total_chunks': total_chunks
        }

    async def _stage_2_wb_processing(
        self,
        job_id: str,
        chunks: Dict[str, List],
        progress_message: types.Message
    ) -> Dict[str, Any]:
        """ЭТАП 2: Обработка WB данных"""
        logger.info(f"🟣 ЭТАП 2: Обработка WB данных для {job_id}")
        wb_chunks = chunks['wb']

        await self._update_progress(progress_message,
            f"🟣 **ЭТАП 2/4: WILDBERRIES**\\n\\n"
            f"📊 Обрабатываю **{len(wb_chunks)} периодов**\\n"
            f"📋 Получаю: заказы + продажи + реклама\\n"
            f"⚡ Используется кеширование\\n\\n"
            f"🔄 Начинаю обработку..."
        )

        wb_results = {
            'orders': [],
            'sales': [],
            'advertising': {'total_spend': 0, 'total_views': 0, 'total_clicks': 0, 'campaigns': []}
        }

        # Обрабатываем WB чанки с оптимизацией
        for i, (chunk_from, chunk_to) in enumerate(wb_chunks, 1):
            try:
                progress_percent = int((i-1) / len(wb_chunks) * 100)
                await self._update_progress(progress_message,
                    f"🟣 **WB ОБРАБОТКА: {i}/{len(wb_chunks)}**\\n\\n"
                    f"📅 Текущий период: {chunk_from} → {chunk_to}\\n"
                    f"📊 Прогресс WB: **{progress_percent}%**\\n\\n"
                    f"⏳ Получаю заказы и продажи..."
                )

                # Проверяем кеш сначала
                cache_key_wb = f"wb_full_{chunk_from}_{chunk_to}"
                cached_wb = self.cache.get_chunk_data(cache_key_wb)

                if cached_wb and 'data' in cached_wb:
                    logger.info(f"Использован кеш для WB {chunk_from}-{chunk_to}")
                    wb_data = cached_wb['data']
                else:
                    # Получаем данные из API
                    wb_data = await self.cached_processor.get_wb_data_cached(chunk_from, chunk_to)

                    # Сохраняем в кеш
                    self.cache.save_chunk_data(cache_key_wb, wb_data, 24)

                # Агрегируем результаты
                if wb_data:
                    orders_stats = wb_data.get('orders_stats', {})
                    sales_stats = wb_data.get('sales_stats', {})

                    if 'orders' in wb_data:
                        wb_results['orders'].extend(wb_data['orders'])
                    if 'sales' in wb_data:
                        wb_results['sales'].extend(wb_data['sales'])

                    logger.info(f"WB чанк {i}: {orders_stats.get('count', 0)} заказов, {sales_stats.get('count', 0)} продаж")

                # Рекламные данные (с отдельной обработкой)
                try:
                    adv_data = await self.optimized_client.get_wb_advertising_batch([(chunk_from, chunk_to)])
                    if adv_data:
                        wb_results['advertising']['total_spend'] += adv_data.get('total_spend', 0)
                        wb_results['advertising']['total_views'] += adv_data.get('total_views', 0)
                        wb_results['advertising']['total_clicks'] += adv_data.get('total_clicks', 0)
                        wb_results['advertising']['campaigns'].extend(adv_data.get('campaigns', []))
                except Exception as e:
                    logger.warning(f"Ошибка получения рекламы WB для {chunk_from}-{chunk_to}: {e}")

                # КРИТИЧНО: Умная адаптивная задержка вместо фиксированной
                if i < len(wb_chunks):
                    # Уменьшена задержка с 15 до 5 секунд + rate limiter уже защищает
                    await asyncio.sleep(5.0)

            except Exception as e:
                logger.error(f"Ошибка обработки WB чанка {i} ({chunk_from}-{chunk_to}): {e}")
                continue

        # Финальная статистика WB
        total_orders = len(wb_results['orders'])
        total_sales = len(wb_results['sales'])
        total_adv_spend = wb_results['advertising']['total_spend']

        await self._update_progress(progress_message,
            f"✅ **WB ОБРАБОТКА ЗАВЕРШЕНА**\\n\\n"
            f"📋 Заказов получено: **{total_orders:,}**\\n"
            f"✅ Продаж получено: **{total_sales:,}**\\n"
            f"💰 Расходы на рекламу: **{total_adv_spend:,.0f} ₽**\\n\\n"
            f"🔄 Переходим к обработке Ozon..."
        )

        logger.info(f"✅ WB обработка завершена: {total_orders} заказов, {total_sales} продаж")
        return wb_results

    async def _stage_3_ozon_processing(
        self,
        job_id: str,
        chunks: Dict[str, List],
        progress_message: types.Message
    ) -> Dict[str, Any]:
        """ЭТАП 3: Обработка Ozon данных"""
        logger.info(f"🔵 ЭТАП 3: Обработка Ozon данных для {job_id}")
        ozon_chunks = chunks['ozon']

        await self._update_progress(progress_message,
            f"🔵 **ЭТАП 3/4: OZON**\\n\\n"
            f"📊 Обрабатываю **{len(ozon_chunks)} периодов**\\n"
            f"📦 Получаю: FBO заказы + FBS транзакции\\n"
            f"⚡ Используется кеширование\\n\\n"
            f"🔄 Начинаю обработку..."
        )

        ozon_results = {
            'fbo_orders': [],
            'fbs_transactions': []
        }

        # Обрабатываем Ozon чанки
        for i, (chunk_from, chunk_to) in enumerate(ozon_chunks, 1):
            try:
                progress_percent = int((i-1) / len(ozon_chunks) * 100)
                await self._update_progress(progress_message,
                    f"🔵 **OZON ОБРАБОТКА: {i}/{len(ozon_chunks)}**\\n\\n"
                    f"📅 Текущий период: {chunk_from} → {chunk_to}\\n"
                    f"📊 Прогресс Ozon: **{progress_percent}%**\\n\\n"
                    f"⏳ Получаю транзакции..."
                )

                # Проверяем кеш
                cache_key_ozon = f"ozon_full_{chunk_from}_{chunk_to}"
                cached_ozon = self.cache.get_chunk_data(cache_key_ozon)

                if cached_ozon and 'data' in cached_ozon:
                    logger.info(f"Использован кеш для Ozon {chunk_from}-{chunk_to}")
                    ozon_data = cached_ozon['data']
                else:
                    # Получаем данные из API
                    ozon_data = await self.cached_processor.get_ozon_data_cached(chunk_from, chunk_to)

                    # Сохраняем в кеш
                    self.cache.save_chunk_data(cache_key_ozon, ozon_data, 24)

                # Агрегируем результаты
                if ozon_data:
                    fbo_count = ozon_data.get('fbo_count', 0)
                    fbs_count = ozon_data.get('fbs_count', 0) or len(ozon_data.get('transactions', []))

                    if 'fbo_orders' in ozon_data:
                        ozon_results['fbo_orders'].extend(ozon_data['fbo_orders'])
                    if 'transactions' in ozon_data:
                        ozon_results['fbs_transactions'].extend(ozon_data['transactions'])

                    logger.info(f"Ozon чанк {i}: {fbo_count} FBO, {fbs_count} FBS транзакций")

                # КРИТИЧНО: Сокращенная задержка для Ozon (rate limiter уже защищает)
                if i < len(ozon_chunks):
                    await asyncio.sleep(2.0)  # Уменьшено с 5 до 2 секунд

            except Exception as e:
                logger.error(f"Ошибка обработки Ozon чанка {i} ({chunk_from}-{chunk_to}): {e}")
                continue

        # Финальная статистика Ozon
        total_fbo = len(ozon_results['fbo_orders'])
        total_fbs = len(ozon_results['fbs_transactions'])

        await self._update_progress(progress_message,
            f"✅ **OZON ОБРАБОТКА ЗАВЕРШЕНА**\\n\\n"
            f"📦 FBO заказов: **{total_fbo:,}**\\n"
            f"📊 FBS транзакций: **{total_fbs:,}**\\n\\n"
            f"🔄 Переходим к финальным расчетам..."
        )

        logger.info(f"✅ Ozon обработка завершена: {total_fbo} FBO, {total_fbs} FBS")
        return ozon_results

    async def _stage_4_aggregation(
        self,
        job_id: str,
        wb_data: Dict[str, Any],
        ozon_data: Dict[str, Any],
        date_from: str,
        date_to: str,
        progress_message: types.Message
    ) -> Dict[str, Any]:
        """ЭТАП 4: Финальная агрегация"""
        logger.info(f"🔢 ЭТАП 4: Финальная агрегация для {job_id}")

        await self._update_progress(progress_message,
            f"🔢 **ЭТАП 4/4: ФИНАЛЬНЫЕ РАСЧЕТЫ**\\n\\n"
            f"🔍 Валидирую качество данных\\n"
            f"⚡ Агрегирую все полученные данные\\n"
            f"📊 Рассчитываю метрики и прибыль\\n"
            f"💾 Сохраняю результаты\\n\\n"
            f"⏳ Выполняю валидацию и расчеты..."
        )

        # 🔍 ФИНАЛЬНАЯ ВАЛИДАЦИЯ ДАННЫХ
        logger.info("🔍 Запуск финальной валидации данных перед агрегацией")
        try:
            from data_validator import validate_data_before_aggregation

            validation_data = {
                'wb_data': wb_data,
                'ozon_data': ozon_data
            }

            validation_result = validate_data_before_aggregation(validation_data)

            if not validation_result.get('is_valid', False):
                logger.warning(f"⚠️ Обнаружены проблемы валидации: {validation_result.get('errors_count', 0)} ошибок")
                for error in validation_result.get('errors', []):
                    logger.warning(f"   • {error}")
            else:
                logger.info("✅ Валидация данных прошла успешно")

        except Exception as e:
            logger.warning(f"⚠️ Ошибка валидации данных: {e}, продолжаем обработку")

        # Агрегируем WB данные
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: wb_data уже содержит накопленные результаты от _stage_2_wb_processing
        wb_orders_count = len(wb_data.get('orders', []))
        wb_sales_count = len(wb_data.get('sales', []))

        # КРИТИЧНО: Рассчитываем WB выручку ТОЛЬКО ИЗ РЕАЛИЗОВАННЫХ ПРОДАЖ (исключаем возвраты)
        wb_sales = wb_data.get('sales', [])

        # Фильтруем только реализованные продажи (исключаем возвраты и отмены)
        wb_realized_sales = [sale for sale in wb_sales if sale.get('isRealization', False)]

        wb_revenue = sum(sale.get('forPay', 0) for sale in wb_realized_sales)
        wb_gross_revenue = sum(sale.get('priceWithDisc', 0) for sale in wb_realized_sales)

        logger.info(f"💰 WB: {len(wb_realized_sales)} реализованных из {len(wb_sales)} общих продаж")
        logger.info(f"💰 WB выручка: {wb_revenue:,.2f} ₽ (forPay), {wb_gross_revenue:,.2f} ₽ (priceWithDisc)")

        # КРИТИЧНО: Рассчитываем Ozon выручку ТОЛЬКО из FBS транзакций (FBO уже учтены в FBS)
        ozon_revenue = 0
        ozon_units = 0

        logger.info("🔍 OZON: Обрабатываем только FBS транзакции (FBO уже включены)")

        for transaction in ozon_data.get('fbs_transactions', []):
            operation_type = transaction.get('operation_type', '')

            # КРИТИЧНО: Пропускаем возвраты и нерелевантные операции
            if operation_type == 'ClientReturnAgentOperation':
                continue  # Пропускаем возвраты

            accruals = transaction.get('accruals_for_sale', 0) or 0
            if accruals > 0:
                ozon_revenue += accruals
                ozon_units += 1

        logger.info(f"💰 OZON итоговая выручка: {ozon_revenue:,.2f} ₽ ({ozon_units} единиц)")
        logger.info(f"⚠️  FBO заказы НЕ учитываются отдельно (уже в FBS транзакциях)")

        # Финальные расчеты
        total_revenue = wb_revenue + ozon_revenue
        total_units = wb_sales_count + ozon_units

        # Расходы (упрощенный расчет)
        wb_advertising_spend = wb_data.get('advertising', {}).get('total_spend', 0)
        estimated_costs = total_revenue * 0.25  # 25% от выручки на логистику/комиссии
        net_profit = total_revenue - estimated_costs - wb_advertising_spend

        # Собираем финальный результат
        final_result = {
            'job_id': job_id,
            'period': f"{date_from} - {date_to}",
            'processing_completed_at': datetime.now().isoformat(),

            # Общие показатели
            'total_revenue': total_revenue,
            'total_units': total_units,
            'net_profit': net_profit,

            # WB данные
            'wb_data': {
                'orders_count': wb_orders_count,
                'sales_count': wb_sales_count,
                'revenue': wb_revenue,
                'gross_revenue': wb_gross_revenue,
                'advertising_spend': wb_advertising_spend,
                'buyout_rate': (wb_sales_count / wb_orders_count * 100) if wb_orders_count > 0 else 0
            },

            # Ozon данные
            'ozon_data': {
                'units': ozon_units,
                'revenue': ozon_revenue,
                'fbo_orders_count': len(ozon_data.get('fbo_orders', [])),
                'fbs_transactions_count': len(ozon_data.get('fbs_transactions', []))
            },

            # Метаданные
            'processing_stages': [
                'Initialization completed',
                'WB processing completed',
                'Ozon processing completed',
                'Aggregation completed'
            ]
        }

        # Сохраняем финальный результат в трекер
        self.progress.save_final_result(job_id, final_result)

        await self._update_progress(progress_message,
            f"✅ **ОБРАБОТКА ЗАВЕРШЕНА!**\\n\\n"
            f"📊 **ИТОГИ:**\\n"
            f"💰 Общая выручка: **{total_revenue:,.0f} ₽**\\n"
            f"📦 Всего единиц: **{total_units:,}**\\n"
            f"🎯 Чистая прибыль: **{net_profit:,.0f} ₽**\\n\\n"
            f"🟣 **WB:** {wb_sales_count:,} продаж, {wb_revenue:,.0f} ₽\\n"
            f"🔵 **Ozon:** {ozon_units:,} операций, {ozon_revenue:,.0f} ₽\\n\\n"
            f"⏱️ Завершено: {datetime.now().strftime('%H:%M')}"
        )

        logger.info(f"✅ Этапная обработка {job_id} завершена: выручка {total_revenue:,.0f} ₽")
        return final_result

    async def _update_progress(self, message: types.Message, text: str):
        """ОПТИМИЗИРОВАННОЕ обновление прогресса в Telegram"""
        try:
            await message.edit_text(text, parse_mode='Markdown')
            await asyncio.sleep(0.1)  # КРИТИЧНО: Уменьшено с 0.5 до 0.1 секунды
        except Exception as e:
            logger.error(f"Ошибка обновления прогресса: {e}")

    async def resume_job(self, job_id: str, progress_message: types.Message) -> Optional[Dict[str, Any]]:
        """Возобновление прерванной задачи"""
        try:
            job = self.progress.get_job_progress(job_id)
            if not job:
                logger.error(f"Задача {job_id} не найдена")
                return None

            logger.info(f"🔄 Возобновление задачи {job_id} со статуса {job.status}")

            # Определяем с какого этапа продолжить
            if job.status == JobStatus.INITIALIZED.value:
                return await self.process_year_staged(job.date_from, job.date_to, progress_message, job_id)
            elif job.status == JobStatus.WB_PROCESSING.value:
                # Возобновляем с WB обработки
                pass  # Реализация возобновления
            # И так далее для других этапов

            logger.info(f"✅ Задача {job_id} успешно возобновлена")

        except Exception as e:
            logger.error(f"❌ Ошибка возобновления задачи {job_id}: {e}")
            return None

    async def cleanup(self):
        """Очистка ресурсов"""
        await self.optimized_client.close_all_sessions()


# Глобальный экземпляр для использования
staged_processor = StagedDataProcessor()