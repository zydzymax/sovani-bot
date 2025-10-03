"""Per-organization limits and quotas (Stage 19).

Implements:
- Rate limiting (RPS per org)
- Export row limits
- Job queue limits
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def check_rate_limit(db: Session, org_id: int, key: str, quota_per_sec: int) -> None:
    """Check and enforce rate limit for organization.

    Args:
        db: Database session
        org_id: Organization ID
        key: Rate limit key (e.g., "pricing_compute", "export")
        quota_per_sec: Maximum requests per second

    Raises:
        HTTPException: 429 if rate limit exceeded

    """
    # Use current second as time bucket
    ts_bucket = int(time.time())

    # Get current count for this bucket
    result = db.execute(
        text(
            """
            SELECT count FROM org_limits_state
            WHERE org_id = :org_id
                AND limit_key = :key
                AND ts_bucket = :ts_bucket
        """
        ),
        {"org_id": org_id, "key": key, "ts_bucket": ts_bucket},
    ).first()

    current_count = result[0] if result else 0

    if current_count >= quota_per_sec:
        logger.warning(f"Rate limit exceeded for org {org_id}, key={key}, bucket={ts_bucket}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {quota_per_sec} requests/second for {key}",
        )

    # Increment or insert
    if current_count > 0:
        db.execute(
            text(
                """
                UPDATE org_limits_state
                SET count = count + 1
                WHERE org_id = :org_id
                    AND limit_key = :key
                    AND ts_bucket = :ts_bucket
            """
            ),
            {"org_id": org_id, "key": key, "ts_bucket": ts_bucket},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO org_limits_state (org_id, limit_key, ts_bucket, count)
                VALUES (:org_id, :key, :ts_bucket, 1)
            """
            ),
            {"org_id": org_id, "key": key, "ts_bucket": ts_bucket},
        )

    db.commit()

    # Cleanup old buckets (older than 5 minutes)
    cleanup_threshold = ts_bucket - 300
    db.execute(
        text("DELETE FROM org_limits_state WHERE ts_bucket < :threshold"),
        {"threshold": cleanup_threshold},
    )
    db.commit()


def check_export_limit(org_id: int, requested_rows: int, max_rows: int | None = None) -> None:
    """Check export row limit for organization.

    Args:
        org_id: Organization ID
        requested_rows: Number of rows requested
        max_rows: Maximum allowed rows (defaults to ORG_EXPORT_MAX_ROWS)

    Raises:
        HTTPException: 400 if limit exceeded

    """
    settings = get_settings()

    if max_rows is None:
        max_rows = settings.org_export_max_rows

    if requested_rows > max_rows:
        logger.warning(f"Export limit exceeded for org {org_id}: {requested_rows} > {max_rows}")
        raise HTTPException(
            status_code=400,
            detail=f"Export row limit exceeded: requested {requested_rows}, max {max_rows} rows",
        )


def check_job_queue_limit(db: Session, org_id: int, max_jobs: int | None = None) -> None:
    """Check job queue limit for organization.

    Args:
        db: Database session
        org_id: Organization ID
        max_jobs: Maximum concurrent jobs (defaults to ORG_MAX_JOBS_ENQUEUED)

    Raises:
        HTTPException: 429 if job queue full

    """
    settings = get_settings()

    if max_jobs is None:
        max_jobs = settings.org_max_jobs_enqueued

    # Count pending/running jobs for this org
    # Assumes job_run table has org_id and status columns
    result = db.execute(
        text(
            """
            SELECT COUNT(*) FROM job_run
            WHERE org_id = :org_id
                AND status IN ('pending', 'running')
        """
        ),
        {"org_id": org_id},
    ).first()

    job_count = result[0] if result else 0

    if job_count >= max_jobs:
        logger.warning(f"Job queue limit exceeded for org {org_id}: {job_count}/{max_jobs}")
        raise HTTPException(
            status_code=429,
            detail=f"Job queue limit exceeded: {job_count}/{max_jobs} concurrent jobs",
        )


def enforce_tenant_scoping(org_id: int) -> dict[str, Any]:
    """Return dict with org_id for scoping SQL queries.

    Args:
        org_id: Organization ID

    Returns:
        Dict with org_id parameter

    """
    settings = get_settings()

    if settings.tenant_enforcement_enabled:
        return {"org_id": org_id}
    else:
        return {}
