"""Scheduler job monitoring service."""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import timezone, datetime
from typing import Any

from app.core.metrics import scheduler_job_duration_seconds, scheduler_jobs_total
from app.db.models import JobRun
from app.db.session import SessionLocal


@contextmanager
def monitor_job(job_name: str, metadata: dict[str, Any] | None = None):
    """Context manager to monitor scheduled job execution.

    Automatically logs job start/finish, tracks duration, and records errors.
    Updates Prometheus metrics and database JobRun table.

    Usage:
        with monitor_job("sync_wb_orders"):
            # Your job code here
            pass

    Args:
        job_name: Name of the scheduled job
        metadata: Optional metadata dict (e.g., records_processed)

    """
    db = SessionLocal()
    start_time = time.time()
    started_at = datetime.now(timezone.utc)

    # Create job run record
    job_run = JobRun(
        job_name=job_name,
        started_at=started_at,
        status="running",
        metadata=metadata or {},
    )
    db.add(job_run)
    db.commit()
    job_run_id = job_run.id

    try:
        yield job_run  # Allow caller to update metadata during execution

        # Job succeeded
        duration = time.time() - start_time
        job_run.status = "success"
        job_run.finished_at = datetime.now(timezone.utc)
        job_run.duration_seconds = duration
        db.commit()

        # Update Prometheus metrics
        scheduler_jobs_total.labels(job_name=job_name, status="success").inc()
        scheduler_job_duration_seconds.labels(job_name=job_name).observe(duration)

    except Exception as e:
        # Job failed
        duration = time.time() - start_time
        job_run.status = "failed"
        job_run.finished_at = datetime.now(timezone.utc)
        job_run.duration_seconds = duration
        job_run.error_message = str(e)[:500]  # Truncate to fit column
        db.commit()

        # Update Prometheus metrics
        scheduler_jobs_total.labels(job_name=job_name, status="failed").inc()
        scheduler_job_duration_seconds.labels(job_name=job_name).observe(duration)

        raise  # Re-raise exception for caller to handle

    finally:
        db.close()


def get_job_status(job_name: str | None = None, limit: int = 100) -> list[dict]:
    """Get recent job execution history.

    Args:
        job_name: Optional job name filter
        limit: Maximum number of records to return

    Returns:
        List of job run dictionaries with status and timing info

    """
    db = SessionLocal()
    try:
        query = db.query(JobRun).order_by(JobRun.started_at.desc()).limit(limit)

        if job_name:
            query = query.filter(JobRun.job_name == job_name)

        runs = query.all()

        return [
            {
                "id": run.id,
                "job_name": run.job_name,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "status": run.status,
                "duration_seconds": run.duration_seconds,
                "error_message": run.error_message,
                "metadata": run.metadata,
            }
            for run in runs
        ]
    finally:
        db.close()


def get_job_statistics(job_name: str) -> dict:
    """Get aggregated statistics for a specific job.

    Args:
        job_name: Name of the job

    Returns:
        Dict with success rate, average duration, recent failures

    """
    db = SessionLocal()
    try:
        # Get last 100 runs
        runs = (
            db.query(JobRun)
            .filter(JobRun.job_name == job_name)
            .order_by(JobRun.started_at.desc())
            .limit(100)
            .all()
        )

        if not runs:
            return {
                "job_name": job_name,
                "total_runs": 0,
                "success_rate": 0.0,
                "avg_duration_seconds": 0.0,
            }

        total_runs = len(runs)
        successful_runs = [r for r in runs if r.status == "success"]
        failed_runs = [r for r in runs if r.status == "failed"]

        success_rate = (len(successful_runs) / total_runs) * 100 if total_runs > 0 else 0.0

        # Calculate average duration (only for completed runs)
        completed_runs = [r for r in runs if r.duration_seconds is not None]
        avg_duration = (
            sum(r.duration_seconds for r in completed_runs) / len(completed_runs)
            if completed_runs
            else 0.0
        )

        return {
            "job_name": job_name,
            "total_runs": total_runs,
            "successful_runs": len(successful_runs),
            "failed_runs": len(failed_runs),
            "success_rate": round(success_rate, 2),
            "avg_duration_seconds": round(avg_duration, 2),
            "last_run": runs[0].started_at.isoformat() if runs else None,
            "last_status": runs[0].status if runs else None,
        }
    finally:
        db.close()
