"""Advanced healthcheck endpoint with dependency checks."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import psutil
from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionLocal
# APP_START_TIME will be passed as parameter or imported at runtime

router = APIRouter()


@router.get("/healthz")
def healthz():
    """Comprehensive health check endpoint.

    Checks:
    - Database connectivity
    - Disk space
    - Memory usage
    - Application uptime

    Returns:
        200 OK if all checks pass
        503 Service Unavailable if any check fails
    """
    status = "healthy"
    checks = {}
    overall_healthy = True

    # 1. Database check
    try:
        db = SessionLocal()
        start = time.time()
        db.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000  # Convert to ms
        db.close()
        checks["database"] = {"status": "ok", "latency_ms": round(latency, 2)}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        overall_healthy = False
        status = "unhealthy"

    # 2. Disk space check
    try:
        disk = psutil.disk_usage("/")
        disk_free_gb = disk.free / (1024**3)
        disk_percent = disk.percent

        if disk_percent > 90:
            checks["disk"] = {
                "status": "warning",
                "free_gb": round(disk_free_gb, 2),
                "used_percent": disk_percent,
            }
            overall_healthy = False
            status = "degraded"
        else:
            checks["disk"] = {
                "status": "ok",
                "free_gb": round(disk_free_gb, 2),
                "used_percent": disk_percent,
            }
    except Exception as e:
        checks["disk"] = {"status": "error", "error": str(e)}
        overall_healthy = False
        status = "unhealthy"

    # 3. Memory check
    try:
        mem = psutil.virtual_memory()
        mem_percent = mem.percent

        if mem_percent > 90:
            checks["memory"] = {
                "status": "warning",
                "available_mb": round(mem.available / (1024**2), 2),
                "used_percent": mem_percent,
            }
            status = "degraded" if status == "healthy" else status
        else:
            checks["memory"] = {
                "status": "ok",
                "available_mb": round(mem.available / (1024**2), 2),
                "used_percent": mem_percent,
            }
    except Exception as e:
        checks["memory"] = {"status": "error", "error": str(e)}
        overall_healthy = False
        status = "unhealthy"

    # 4. Uptime (read from /proc/uptime on Linux)
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
    except Exception:
        # Fallback: use process uptime
        uptime_seconds = time.time() - psutil.Process(os.getpid()).create_time()
    checks["uptime"] = {
        "status": "ok",
        "uptime_seconds": round(uptime_seconds, 2),
        "uptime_human": _format_uptime(uptime_seconds),
    }

    # 5. Current time
    checks["timestamp"] = datetime.now(timezone.utc).isoformat()

    response = {
        "status": status,
        "healthy": overall_healthy,
        "checks": checks,
    }

    # Return 503 if unhealthy
    if not overall_healthy:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=response)

    return response


@router.get("/jobs/status")
def jobs_status(job_name: str | None = None, limit: int = 50):
    """Get scheduler job execution history.

    Args:
        job_name: Optional filter by job name
        limit: Maximum number of records (default 50)

    Returns:
        List of recent job executions with status and timing

    """
    from app.services.job_monitoring import get_job_status

    return {"jobs": get_job_status(job_name=job_name, limit=limit)}


@router.get("/jobs/stats/{job_name}")
def job_statistics(job_name: str):
    """Get aggregated statistics for a specific job.

    Args:
        job_name: Name of the job

    Returns:
        Success rate, average duration, failure count

    """
    from app.services.job_monitoring import get_job_statistics

    return get_job_statistics(job_name)


def _format_uptime(seconds: float) -> str:
    """Format uptime in human-readable format.

    Args:
        seconds: Uptime in seconds

    Returns:
        Human-readable uptime string (e.g., "1d 2h 30m")

    """
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")

    return " ".join(parts)
