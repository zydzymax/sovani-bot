"""Фоновые задачи Celery для обработки больших периодов данных"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from real_data_reports import RealDataFinancialReports

from api_chunking import APIChunker
from celery_config import celery_app
from chunk_cache import ChunkCache
from progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)

# Инициализация компонентов
reports = RealDataFinancialReports()
cache = ChunkCache()
progress = ProgressTracker()


@celery_app.task(
    bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60}
)
def process_wb_chunk(
    self, chunk_from: str, chunk_to: str, job_id: str, chunk_index: int, total_chunks: int
):
    """Фоновая обработка одного чанка WB данных"""
    try:
        logger.info(f"Обработка WB чанка {chunk_index}/{total_chunks}: {chunk_from} - {chunk_to}")

        # Проверяем кеш
        cache_key = f"wb_chunk_{chunk_from}_{chunk_to}"
        cached_result = cache.get_chunk_data(cache_key)

        if cached_result:
            logger.info(f"Найден кеш для WB чанка {chunk_from}-{chunk_to}")
            progress.update_chunk_progress(job_id, chunk_index, "wb", "completed", cached_result)
            return cached_result

        # Обновляем прогресс
        progress.update_chunk_progress(job_id, chunk_index, "wb", "processing", None)

        # Выполняем обработку
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(reports.get_real_wb_data(chunk_from, chunk_to))
        finally:
            loop.close()

        # Сохраняем в кеш
        cache.save_chunk_data(cache_key, result, expiry_hours=24)

        # Обновляем прогресс
        progress.update_chunk_progress(job_id, chunk_index, "wb", "completed", result)

        logger.info(
            f"WB чанк {chunk_index} завершен: {result.get('orders_stats', {}).get('count', 0)} заказов"
        )
        return result

    except Exception as e:
        logger.error(f"Ошибка обработки WB чанка {chunk_from}-{chunk_to}: {e}")
        progress.update_chunk_progress(job_id, chunk_index, "wb", "failed", None)
        raise


@celery_app.task(
    bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60}
)
def process_ozon_chunk(
    self, chunk_from: str, chunk_to: str, job_id: str, chunk_index: int, total_chunks: int
):
    """Фоновая обработка одного чанка Ozon данных"""
    try:
        logger.info(f"Обработка Ozon чанка {chunk_index}/{total_chunks}: {chunk_from} - {chunk_to}")

        # Проверяем кеш
        cache_key = f"ozon_chunk_{chunk_from}_{chunk_to}"
        cached_result = cache.get_chunk_data(cache_key)

        if cached_result:
            logger.info(f"Найден кеш для Ozon чанка {chunk_from}-{chunk_to}")
            progress.update_chunk_progress(job_id, chunk_index, "ozon", "completed", cached_result)
            return cached_result

        # Обновляем прогресс
        progress.update_chunk_progress(job_id, chunk_index, "ozon", "processing", None)

        # Выполняем обработку
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(reports.get_real_ozon_sales(chunk_from, chunk_to))
        finally:
            loop.close()

        # Сохраняем в кеш
        cache.save_chunk_data(cache_key, result, expiry_hours=24)

        # Обновляем прогресс
        progress.update_chunk_progress(job_id, chunk_index, "ozon", "completed", result)

        logger.info(f"Ozon чанк {chunk_index} завершен: {result.get('units', 0)} операций")
        return result

    except Exception as e:
        logger.error(f"Ошибка обработки Ozon чанка {chunk_from}-{chunk_to}: {e}")
        progress.update_chunk_progress(job_id, chunk_index, "ozon", "failed", None)
        raise


@celery_app.task(bind=True)
def aggregate_final_results(self, job_id: str, date_from: str, date_to: str):
    """Финальная агрегация всех результатов"""
    try:
        logger.info(f"Начинаем финальную агрегацию для задачи {job_id}")

        # Получаем все результаты чанков
        wb_results = progress.get_completed_chunks(job_id, "wb")
        ozon_results = progress.get_completed_chunks(job_id, "ozon")

        logger.info(f"Агрегируем: {len(wb_results)} WB чанков, {len(ozon_results)} Ozon чанков")

        # Агрегируем WB данные
        wb_aggregated = aggregate_wb_data(wb_results)

        # Агрегируем Ozon данные
        ozon_aggregated = aggregate_ozon_data(ozon_results)

        # Финальный расчет
        final_result = {
            "period": f"{date_from} - {date_to}",
            "total_revenue": wb_aggregated.get("sales_stats", {}).get("for_pay", 0)
            + ozon_aggregated.get("revenue", 0),
            "total_units": wb_aggregated.get("sales_stats", {}).get("count", 0)
            + ozon_aggregated.get("units", 0),
            "wb_data": wb_aggregated,
            "ozon_data": ozon_aggregated,
            "processing_time": datetime.now().isoformat(),
            "job_id": job_id,
        }

        # Рассчитываем чистую прибыль
        total_revenue = final_result["total_revenue"]
        final_result["net_profit"] = total_revenue * 0.7  # Примерно 30% расходов

        # Сохраняем финальный результат
        progress.save_final_result(job_id, final_result)

        logger.info(f"Финальная агрегация завершена: выручка {total_revenue:,.0f} ₽")
        return final_result

    except Exception as e:
        logger.error(f"Ошибка финальной агрегации для {job_id}: {e}")
        raise


def aggregate_wb_data(wb_results: list[dict]) -> dict[str, Any]:
    """Агрегация WB данных из всех чанков"""
    total_orders_count = 0
    total_orders_revenue = 0
    total_sales_count = 0
    total_sales_revenue = 0

    for result in wb_results:
        if not result or "data" not in result:
            continue

        data = result["data"]
        orders_stats = data.get("orders_stats", {})
        sales_stats = data.get("sales_stats", {})

        total_orders_count += orders_stats.get("count", 0)
        total_orders_revenue += orders_stats.get("price_with_disc", 0)
        total_sales_count += sales_stats.get("count", 0)
        total_sales_revenue += sales_stats.get("for_pay", 0)

    return {
        "orders_stats": {"count": total_orders_count, "price_with_disc": total_orders_revenue},
        "sales_stats": {"count": total_sales_count, "for_pay": total_sales_revenue},
        "buyout_rate": (
            (total_sales_count / total_orders_count * 100) if total_orders_count > 0 else 0
        ),
    }


def aggregate_ozon_data(ozon_results: list[dict]) -> dict[str, Any]:
    """Агрегация Ozon данных из всех чанков"""
    total_revenue = 0
    total_units = 0
    total_commission = 0

    for result in ozon_results:
        if not result or "data" not in result:
            continue

        data = result["data"]
        total_revenue += data.get("revenue", 0)
        total_units += data.get("units", 0)
        total_commission += data.get("commission", 0)

    return {"revenue": total_revenue, "units": total_units, "commission": total_commission}


@celery_app.task(bind=True)
def process_year_data_background(
    self, date_from: str, date_to: str, telegram_chat_id: int, job_id: str = None
):
    """Главная фоновая задача обработки годовых данных"""
    try:
        if not job_id:
            job_id = f"year_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Запуск фоновой обработки года {date_from}-{date_to}, job_id: {job_id}")

        # Инициализация прогресса
        progress.initialize_job(job_id, date_from, date_to, telegram_chat_id)

        # Разбиваем период на чанки
        wb_chunks = APIChunker.chunk_date_range(date_from, date_to, "wb_sales")
        ozon_chunks = APIChunker.chunk_date_range(date_from, date_to, "ozon_fbo")

        total_chunks = len(wb_chunks) + len(ozon_chunks)
        logger.info(f"Создано {len(wb_chunks)} WB чанков и {len(ozon_chunks)} Ozon чанков")

        # Запускаем обработку WB чанков
        wb_tasks = []
        for i, (chunk_from, chunk_to) in enumerate(wb_chunks):
            task = process_wb_chunk.delay(chunk_from, chunk_to, job_id, i, len(wb_chunks))
            wb_tasks.append(task)

        # Ждем завершения WB обработки
        wb_results = []
        for task in wb_tasks:
            result = task.get(timeout=3600)  # 1 час на чанк
            wb_results.append(result)

        logger.info(f"Завершена обработка WB данных: {len(wb_results)} чанков")

        # Запускаем обработку Ozon чанков
        ozon_tasks = []
        for i, (chunk_from, chunk_to) in enumerate(ozon_chunks):
            task = process_ozon_chunk.delay(chunk_from, chunk_to, job_id, i, len(ozon_chunks))
            ozon_tasks.append(task)

        # Ждем завершения Ozon обработки
        ozon_results = []
        for task in ozon_tasks:
            result = task.get(timeout=3600)  # 1 час на чанк
            ozon_results.append(result)

        logger.info(f"Завершена обработка Ozon данных: {len(ozon_results)} чанков")

        # Финальная агрегация
        final_task = aggregate_final_results.delay(job_id, date_from, date_to)
        final_result = final_task.get(timeout=300)  # 5 минут на агрегацию

        # Отправляем уведомление в Telegram
        progress.mark_job_completed(job_id, final_result)

        logger.info(f"Фоновая обработка {job_id} завершена успешно")
        return final_result

    except Exception as e:
        logger.error(f"Ошибка фоновой обработки {job_id}: {e}")
        progress.mark_job_failed(job_id, str(e))
        raise


@celery_app.task
def cleanup_old_cache():
    """Очистка старого кеша и результатов"""
    try:
        logger.info("Запуск очистки старого кеша")
        cache.cleanup_expired()
        progress.cleanup_old_jobs(days=7)
        logger.info("Очистка кеша завершена")
    except Exception as e:
        logger.error(f"Ошибка очистки кеша: {e}")


# Периодические задачи (если нужны)
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "cleanup-cache-daily": {
        "task": "background_tasks.cleanup_old_cache",
        "schedule": crontab(hour=2, minute=0),  # Каждый день в 2:00
    },
}
celery_app.conf.timezone = "Europe/Moscow"
