"""
Система отслеживания прогресса обработки больших периодов данных
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import redis
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class JobStatus(Enum):
    INITIALIZED = "initialized"
    WB_PROCESSING = "wb_processing"
    OZON_PROCESSING = "ozon_processing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ChunkProgress:
    chunk_id: str
    platform: str  # 'wb' or 'ozon'
    date_from: str
    date_to: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    result_data: Optional[Dict] = None


@dataclass
class JobProgress:
    job_id: str
    status: str
    date_from: str
    date_to: str
    telegram_chat_id: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_wb_chunks: int = 0
    total_ozon_chunks: int = 0
    completed_wb_chunks: int = 0
    completed_ozon_chunks: int = 0
    error_message: Optional[str] = None
    final_result: Optional[Dict] = None


class ProgressTracker:
    """Отслеживание прогресса фоновых задач"""

    def __init__(self, redis_url: str = "redis://localhost:6379/3"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.job_prefix = "job:"
        self.chunk_prefix = "chunk:"

    def initialize_job(self, job_id: str, date_from: str, date_to: str, telegram_chat_id: int) -> JobProgress:
        """Инициализация новой задачи"""
        try:
            job = JobProgress(
                job_id=job_id,
                status=JobStatus.INITIALIZED.value,
                date_from=date_from,
                date_to=date_to,
                telegram_chat_id=telegram_chat_id,
                created_at=datetime.now().isoformat()
            )

            # Сохраняем в Redis
            job_key = f"{self.job_prefix}{job_id}"
            self.redis_client.setex(job_key, 7 * 24 * 3600, json.dumps(asdict(job)))  # 7 дней TTL

            logger.info(f"Инициализирована задача {job_id}")
            return job

        except Exception as e:
            logger.error(f"Ошибка инициализации задачи {job_id}: {e}")
            raise

    def get_job_progress(self, job_id: str) -> Optional[JobProgress]:
        """Получение прогресса задачи"""
        try:
            job_key = f"{self.job_prefix}{job_id}"
            job_data = self.redis_client.get(job_key)

            if job_data:
                data = json.loads(job_data)
                return JobProgress(**data)

            return None

        except Exception as e:
            logger.error(f"Ошибка получения прогресса задачи {job_id}: {e}")
            return None

    def update_job_status(self, job_id: str, status: JobStatus, **kwargs):
        """Обновление статуса задачи"""
        try:
            job = self.get_job_progress(job_id)
            if job:
                job.status = status.value

                # Обновляем дополнительные поля
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)

                # Сохраняем обновленную задачу
                job_key = f"{self.job_prefix}{job_id}"
                self.redis_client.setex(job_key, 7 * 24 * 3600, json.dumps(asdict(job)))

                logger.info(f"Обновлен статус задачи {job_id}: {status.value}")

        except Exception as e:
            logger.error(f"Ошибка обновления статуса задачи {job_id}: {e}")

    def update_chunk_progress(
        self,
        job_id: str,
        chunk_index: int,
        platform: str,
        status: str,
        result_data: Optional[Dict] = None,
        error_message: Optional[str] = None
    ):
        """Обновление прогресса обработки чанка"""
        try:
            chunk_id = f"{job_id}_{platform}_{chunk_index}"
            chunk_key = f"{self.chunk_prefix}{chunk_id}"

            # Получаем существующий чанк или создаем новый
            existing_data = self.redis_client.get(chunk_key)
            if existing_data:
                chunk = ChunkProgress(**json.loads(existing_data))
            else:
                chunk = ChunkProgress(
                    chunk_id=chunk_id,
                    platform=platform,
                    date_from="",  # Будет обновлено
                    date_to="",    # Будет обновлено
                    status=status
                )

            # Обновляем статус
            chunk.status = status

            if status == ChunkStatus.PROCESSING.value and not chunk.started_at:
                chunk.started_at = datetime.now().isoformat()
            elif status in [ChunkStatus.COMPLETED.value, ChunkStatus.FAILED.value]:
                chunk.completed_at = datetime.now().isoformat()
                if result_data:
                    chunk.result_data = result_data
                if error_message:
                    chunk.error_message = error_message

            # Сохраняем чанк
            self.redis_client.setex(chunk_key, 7 * 24 * 3600, json.dumps(asdict(chunk)))

            # Обновляем счетчики в основной задаче
            self._update_job_counters(job_id, platform, status)

            logger.info(f"Обновлен прогресс чанка {chunk_id}: {status}")

        except Exception as e:
            logger.error(f"Ошибка обновления прогресса чанка: {e}")

    def _update_job_counters(self, job_id: str, platform: str, status: str):
        """Обновление счетчиков завершенных чанков в задаче"""
        job = self.get_job_progress(job_id)
        if not job:
            return

        if status == ChunkStatus.COMPLETED.value:
            if platform == 'wb':
                job.completed_wb_chunks += 1
            elif platform == 'ozon':
                job.completed_ozon_chunks += 1

        # Сохраняем обновленную задачу
        job_key = f"{self.job_prefix}{job_id}"
        self.redis_client.setex(job_key, 7 * 24 * 3600, json.dumps(asdict(job)))

    def get_completed_chunks(self, job_id: str, platform: str) -> List[Dict]:
        """Получение всех завершенных чанков для платформы"""
        try:
            pattern = f"{self.chunk_prefix}{job_id}_{platform}_*"
            chunk_keys = self.redis_client.keys(pattern)

            completed_chunks = []
            for key in chunk_keys:
                chunk_data = self.redis_client.get(key)
                if chunk_data:
                    chunk = json.loads(chunk_data)
                    if chunk.get('status') == ChunkStatus.COMPLETED.value and chunk.get('result_data'):
                        completed_chunks.append(chunk)

            return completed_chunks

        except Exception as e:
            logger.error(f"Ошибка получения завершенных чанков для {job_id}-{platform}: {e}")
            return []

    def get_job_statistics(self, job_id: str) -> Dict[str, Any]:
        """Получение детальной статистики задачи"""
        try:
            job = self.get_job_progress(job_id)
            if not job:
                return {'error': 'Job not found'}

            # Получаем все чанки задачи
            pattern = f"{self.chunk_prefix}{job_id}_*"
            chunk_keys = self.redis_client.keys(pattern)

            chunk_stats = {
                'total_chunks': len(chunk_keys),
                'completed_chunks': 0,
                'failed_chunks': 0,
                'processing_chunks': 0,
                'wb_chunks': 0,
                'ozon_chunks': 0
            }

            for key in chunk_keys:
                chunk_data = self.redis_client.get(key)
                if chunk_data:
                    chunk = json.loads(chunk_data)
                    status = chunk.get('status', '')
                    platform = chunk.get('platform', '')

                    if status == ChunkStatus.COMPLETED.value:
                        chunk_stats['completed_chunks'] += 1
                    elif status == ChunkStatus.FAILED.value:
                        chunk_stats['failed_chunks'] += 1
                    elif status == ChunkStatus.PROCESSING.value:
                        chunk_stats['processing_chunks'] += 1

                    if platform == 'wb':
                        chunk_stats['wb_chunks'] += 1
                    elif platform == 'ozon':
                        chunk_stats['ozon_chunks'] += 1

            # Рассчитываем прогресс
            total_chunks = chunk_stats['total_chunks']
            completed = chunk_stats['completed_chunks']
            progress_percent = (completed / total_chunks * 100) if total_chunks > 0 else 0

            return {
                'job': asdict(job),
                'chunks': chunk_stats,
                'progress_percent': round(progress_percent, 1),
                'estimated_completion': self._estimate_completion(job, chunk_stats)
            }

        except Exception as e:
            logger.error(f"Ошибка получения статистики задачи {job_id}: {e}")
            return {'error': str(e)}

    def _estimate_completion(self, job: JobProgress, chunk_stats: Dict) -> Optional[str]:
        """Оценка времени завершения"""
        try:
            if job.status == JobStatus.COMPLETED.value:
                return None

            completed = chunk_stats['completed_chunks']
            total = chunk_stats['total_chunks']

            if completed == 0:
                return None

            # Рассчитываем среднее время на чанк
            if job.started_at:
                started_time = datetime.fromisoformat(job.started_at)
                elapsed_minutes = (datetime.now() - started_time).total_seconds() / 60
                avg_time_per_chunk = elapsed_minutes / completed

                remaining_chunks = total - completed
                estimated_minutes = remaining_chunks * avg_time_per_chunk

                estimated_completion = datetime.now() + timedelta(minutes=estimated_minutes)
                return estimated_completion.strftime('%H:%M')

            return None

        except Exception as e:
            logger.error(f"Ошибка оценки времени завершения: {e}")
            return None

    def save_final_result(self, job_id: str, result: Dict[str, Any]):
        """Сохранение финального результата"""
        try:
            job = self.get_job_progress(job_id)
            if job:
                job.final_result = result
                job.status = JobStatus.COMPLETED.value
                job.completed_at = datetime.now().isoformat()

                job_key = f"{self.job_prefix}{job_id}"
                self.redis_client.setex(job_key, 7 * 24 * 3600, json.dumps(asdict(job)))

                logger.info(f"Сохранен финальный результат для {job_id}")

        except Exception as e:
            logger.error(f"Ошибка сохранения финального результата для {job_id}: {e}")

    def mark_job_completed(self, job_id: str, result: Dict[str, Any]):
        """Отметка задачи как завершенной"""
        self.save_final_result(job_id, result)

    def mark_job_failed(self, job_id: str, error_message: str):
        """Отметка задачи как провалившейся"""
        self.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=error_message,
            completed_at=datetime.now().isoformat()
        )

    def cleanup_old_jobs(self, days: int = 7):
        """Очистка старых задач"""
        try:
            pattern = f"{self.job_prefix}*"
            job_keys = self.redis_client.keys(pattern)

            deleted = 0
            cutoff_time = datetime.now() - timedelta(days=days)

            for key in job_keys:
                job_data = self.redis_client.get(key)
                if job_data:
                    job = json.loads(job_data)
                    created_at = datetime.fromisoformat(job.get('created_at', ''))

                    if created_at < cutoff_time:
                        # Удаляем задачу и все ее чанки
                        job_id = job.get('job_id', '')
                        chunk_pattern = f"{self.chunk_prefix}{job_id}_*"
                        chunk_keys = self.redis_client.keys(chunk_pattern)

                        self.redis_client.delete(key)
                        if chunk_keys:
                            self.redis_client.delete(*chunk_keys)

                        deleted += 1

            logger.info(f"Очистка завершена: удалено {deleted} старых задач")
            return deleted

        except Exception as e:
            logger.error(f"Ошибка очистки старых задач: {e}")
            return 0

    def get_active_jobs(self) -> List[Dict]:
        """Получение списка активных задач"""
        try:
            pattern = f"{self.job_prefix}*"
            job_keys = self.redis_client.keys(pattern)

            active_jobs = []
            for key in job_keys:
                job_data = self.redis_client.get(key)
                if job_data:
                    job = json.loads(job_data)
                    if job.get('status') not in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                        active_jobs.append(job)

            return sorted(active_jobs, key=lambda x: x.get('created_at', ''))

        except Exception as e:
            logger.error(f"Ошибка получения активных задач: {e}")
            return []