"""Конфигурация Celery для фоновых задач обработки данных"""

import os

from celery import Celery

# Конфигурация Redis (используем тот же экземпляр что и для кеширования)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

# Создание экземпляра Celery
celery_app = Celery(
    "sovani_data_processor",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["background_tasks"],
)

# Конфигурация Celery
celery_app.conf.update(
    # Часовой пояс
    timezone="Europe/Moscow",
    # Сериализация
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Время жизни результатов
    result_expires=3600 * 24 * 7,  # 7 дней
    # Настройки воркеров
    worker_prefetch_multiplier=1,  # По одной задаче на воркера
    task_acks_late=True,  # Подтверждение после выполнения
    worker_max_tasks_per_child=50,  # Перезапуск воркера после 50 задач
    # Ограничения по времени
    task_soft_time_limit=3600 * 2,  # 2 часа - мягкий лимит
    task_time_limit=3600 * 3,  # 3 часа - жесткий лимит
    # Роутинг задач
    task_routes={
        "background_tasks.process_wb_chunk": {"queue": "wb_processing"},
        "background_tasks.process_ozon_chunk": {"queue": "ozon_processing"},
        "background_tasks.aggregate_final_results": {"queue": "aggregation"},
        "background_tasks.process_year_data_background": {"queue": "main_processing"},
    },
    # Автоматическое создание очередей
    task_create_missing_queues=True,
    # Настройки повторов
    task_default_retry_delay=60,  # 1 минута
    task_max_retries=3,
    # Мониторинг
    worker_send_task_events=True,
    task_send_sent_event=True,
)

if __name__ == "__main__":
    celery_app.start()
