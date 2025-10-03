"""Database utilities for org-scoped queries (Stage 19)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlalchemy.orm import Session

from app.core.metrics import tenant_unscoped_query_total

logger = logging.getLogger(__name__)


def exec_scoped(
    db: Session,
    sql: str,
    params: dict[str, Any] | None = None,
    org_id: int | None = None,
) -> Result:
    """Execute SQL with mandatory org_id scoping.

    Args:
        db: Database session
        sql: SQL query string
        params: Query parameters
        org_id: Organization ID (required for scoped queries)

    Returns:
        SQLAlchemy Result

    Raises:
        RuntimeError: If org_id missing or SQL doesn't filter by org_id

    Usage:
        >>> rows = exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id=1)

    """
    # Check if org_id is provided
    if org_id is None:
        tenant_unscoped_query_total.labels(error_type="missing_org_id").inc()
        logger.error(f"exec_scoped called without org_id for SQL: {sql[:100]}...")
        raise RuntimeError("org_id is required for scoped queries")

    # Normalize SQL for checking (add spaces around to avoid false positives)
    sql_normalized = f" {sql.lower()} "

    # Check if SQL contains org_id filter
    if "org_id" not in sql_normalized:
        tenant_unscoped_query_total.labels(error_type="missing_filter").inc()
        logger.error(f"Unscoped SQL detected (missing org_id): {sql[:200]}...")
        raise RuntimeError("Scoped SQL must contain org_id filter in WHERE clause")

    # Merge org_id into params
    merged_params = dict(params or {})
    merged_params["org_id"] = org_id

    # Execute query
    try:
        return db.execute(text(sql), merged_params)
    except Exception as e:
        logger.error(f"exec_scoped failed: {e}, SQL: {sql[:200]}..., org_id: {org_id}")
        raise


def exec_unscoped(db: Session, sql: str, params: dict[str, Any] | None = None) -> Result:
    """Execute SQL without org scoping (use sparingly for admin/system queries).

    Args:
        db: Database session
        sql: SQL query string
        params: Query parameters

    Returns:
        SQLAlchemy Result

    Warning:
        Only use for system queries (migrations, admin ops). All business queries
        should use exec_scoped() to prevent data leaks.

    """
    logger.warning(f"exec_unscoped called for SQL: {sql[:100]}... (use with caution)")
    return db.execute(text(sql), params or {})
