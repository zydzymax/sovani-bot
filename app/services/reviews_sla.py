"""Reviews SLA service - TTFR tracking and backlog management (Stage 18)."""

from __future__ import annotations

import logging
from datetime import timezone, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import (
    reviews_answer_kind_total,
    reviews_sla_within_total,
    reviews_ttfr_seconds,
)
from app.db.utils import exec_scoped

logger = logging.getLogger(__name__)


def update_first_reply_timestamp(
    db: Session,
    *,
    org_id: int,
    review_id: int,
    when: datetime | None = None,
    reply_kind: str | None = None,
) -> None:
    """Update first_reply_at_utc timestamp idempotently.

    Args:
        db: Database session
        org_id: Organization ID for scoping
        review_id: Review ID
        when: Timestamp of reply (default: now UTC)
        reply_kind: 'template' or 'ai' (from Answer Engine)

    Notes:
        - Only sets first_reply_at_utc if currently NULL
        - Ensures accurate TTFR tracking
        - Called from Answer Engine after successful reply post

    """
    if when is None:
        when = datetime.now(timezone.utc)

    # Idempotent update - only set if NULL (scoped to org)
    query = """
        UPDATE reviews
        SET
            first_reply_at_utc = :when,
            reply_kind = :reply_kind
        WHERE id = :review_id
            AND org_id = :org_id
            AND first_reply_at_utc IS NULL
    """

    # Get review to calculate TTFR (scoped to org)
    review_query = (
        "SELECT created_at_utc, marketplace FROM reviews WHERE id = :review_id AND org_id = :org_id"
    )
    review_row = exec_scoped(db, review_query, {"review_id": review_id}, org_id).first()

    result = exec_scoped(
        db,
        query,
        {"review_id": review_id, "when": when, "reply_kind": reply_kind},
        org_id,
    )
    db.commit()

    if result.rowcount > 0:
        logger.info(f"Set first_reply_at_utc for review {review_id}: {when} ({reply_kind})")

        # Update Prometheus metrics
        if review_row:
            created_at, marketplace = review_row
            ttfr_seconds = (when - created_at).total_seconds()

            # Track TTFR histogram
            reviews_ttfr_seconds.labels(marketplace=marketplace).observe(ttfr_seconds)

            # Track reply kind
            if reply_kind:
                reviews_answer_kind_total.labels(kind=reply_kind).inc()

            # Track SLA compliance
            settings = get_settings()
            sla_hours = settings.sla_first_reply_hours
            within_sla = (ttfr_seconds / 3600) <= sla_hours

            reviews_sla_within_total.labels(status="ok" if within_sla else "fail").inc()


def compute_review_sla(
    db: Session,
    *,
    org_id: int,
    d_from: datetime,
    d_to: datetime,
    marketplace: str | None = None,
    sku_id: int | None = None,
) -> dict[str, Any]:
    """Compute SLA metrics for date range.

    Args:
        db: Database session
        org_id: Organization ID for scoping
        d_from: Start date
        d_to: End date
        marketplace: Optional marketplace filter
        sku_id: Optional SKU filter

    Returns:
        Dict with aggregates:
            - count_total: Total reviews
            - replied: Reviews with first_reply_at_utc
            - within_sla: Reviews replied within SLA window
            - share_within_sla: % within SLA
            - median_ttfr_min: Median TTFR in minutes
            - by_marketplace: Breakdown by marketplace
            - by_reply_kind: Breakdown by reply kind (template/ai)

    """
    settings = get_settings()

    # Build base query with filters (scoped to org)
    where_clauses = ["org_id = :org_id", "created_at_utc BETWEEN :d_from AND :d_to"]
    params = {
        "org_id": org_id,
        "d_from": d_from,
        "d_to": d_to,
        "sla_hours": settings.sla_first_reply_hours,
    }

    if marketplace:
        where_clauses.append("marketplace = :marketplace")
        params["marketplace"] = marketplace

    if sku_id:
        where_clauses.append("sku_id = :sku_id")
        params["sku_id"] = sku_id

    where_clause = " AND ".join(where_clauses)

    # Main aggregates
    query = f"""
        SELECT
            COUNT(*) AS count_total,
            SUM(CASE WHEN first_reply_at_utc IS NOT NULL THEN 1 ELSE 0 END) AS replied,
            SUM(within_sla) AS within_sla
        FROM vw_reviews_sla
        WHERE {where_clause}
    """

    result = exec_scoped(db, query, params, org_id).first()
    count_total, replied, within_sla = result or (0, 0, 0)

    # Calculate share
    share_within_sla = (within_sla / replied * 100) if replied > 0 else 0.0

    # Median TTFR (using percentile or approximate median)
    median_query = f"""
        SELECT AVG(ttfr_minutes) AS median_ttfr
        FROM (
            SELECT ttfr_minutes
            FROM vw_reviews_sla
            WHERE {where_clause}
                AND ttfr_minutes IS NOT NULL
            ORDER BY ttfr_minutes
            LIMIT 2
            OFFSET (SELECT COUNT(*) FROM vw_reviews_sla
                    WHERE {where_clause} AND ttfr_minutes IS NOT NULL) / 2 - 1
        )
    """

    median_result = exec_scoped(db, median_query, params, org_id).scalar()
    median_ttfr_min = float(median_result) if median_result else 0.0

    # Breakdown by marketplace
    by_marketplace_query = f"""
        SELECT
            marketplace,
            COUNT(*) AS total,
            SUM(CASE WHEN first_reply_at_utc IS NOT NULL THEN 1 ELSE 0 END) AS replied,
            SUM(within_sla) AS within_sla
        FROM vw_reviews_sla
        WHERE {where_clause}
        GROUP BY marketplace
        ORDER BY marketplace
    """

    by_marketplace = []
    for row in exec_scoped(db, by_marketplace_query, params, org_id):
        mp_total = row[1]
        mp_replied = row[2]
        mp_within_sla = row[3]
        by_marketplace.append(
            {
                "marketplace": row[0],
                "total": mp_total,
                "replied": mp_replied,
                "within_sla": mp_within_sla,
                "share_within_sla": (mp_within_sla / mp_replied * 100) if mp_replied > 0 else 0.0,
            }
        )

    # Breakdown by reply_kind
    by_reply_kind_query = f"""
        SELECT
            COALESCE(reply_kind, 'unknown') AS reply_kind,
            COUNT(*) AS count
        FROM vw_reviews_sla
        WHERE {where_clause}
            AND first_reply_at_utc IS NOT NULL
        GROUP BY reply_kind
        ORDER BY count DESC
    """

    by_reply_kind = [
        {"reply_kind": row[0], "count": row[1]}
        for row in exec_scoped(db, by_reply_kind_query, params, org_id)
    ]

    return {
        "count_total": count_total,
        "replied": replied,
        "within_sla": within_sla,
        "share_within_sla": round(share_within_sla, 2),
        "median_ttfr_min": round(median_ttfr_min, 2),
        "by_marketplace": by_marketplace,
        "by_reply_kind": by_reply_kind,
    }


def find_overdue_reviews(
    db: Session,
    *,
    org_id: int,
    now: datetime,
    escalate_after_hours: int,
    limit: int,
    marketplace: str | None = None,
) -> list[dict[str, Any]]:
    """Find overdue reviews without first reply.

    Args:
        db: Database session
        org_id: Organization ID for scoping
        now: Current timestamp
        escalate_after_hours: Threshold for escalation
        limit: Maximum reviews to return
        marketplace: Optional marketplace filter

    Returns:
        List of overdue reviews sorted by priority:
            1. Negative (rating <=2) + ai_needed=True
            2. Negative (rating <=2) + ai_needed=False
            3. Neutral (rating=3) + ai_needed=True
            4. Neutral (rating=3) + ai_needed=False
            5. Positive (rating>=4) + ai_needed=True
            6. Positive (rating>=4) + ai_needed=False

        Each item contains:
            - review_id
            - marketplace
            - rating
            - has_media
            - ai_needed
            - created_at_utc
            - age_hours
            - sku_id, article
            - link (if available)

    """
    cutoff = now - timedelta(hours=escalate_after_hours)

    where_clauses = [
        "r.org_id = :org_id",
        "r.first_reply_at_utc IS NULL",
        "r.created_at_utc <= :cutoff",
    ]
    params = {"org_id": org_id, "cutoff": cutoff, "limit": limit}

    if marketplace:
        where_clauses.append("r.marketplace = :marketplace")
        params["marketplace"] = marketplace

    where_clause = " AND ".join(where_clauses)

    # Priority calculation:
    # - rating_priority: 1 (negative) < 2 (neutral) < 3 (positive)
    # - ai_needed: 0 (True) < 1 (False)
    query = f"""
        SELECT
            r.id AS review_id,
            r.marketplace,
            r.rating,
            r.has_media,
            (COALESCE(length(NULLIF(r.text, '')), 0) >= 40 OR r.has_media = 1) AS ai_needed,
            r.created_at_utc,
            CAST((julianday(:now) - julianday(r.created_at_utc)) * 24 AS REAL) AS age_hours,
            r.sku_id,
            s.article,
            r.external_id,
            CASE
                WHEN r.rating <= 2 THEN 1
                WHEN r.rating = 3 THEN 2
                ELSE 3
            END AS rating_priority,
            CASE
                WHEN (COALESCE(length(NULLIF(r.text, '')), 0) >= 40 OR r.has_media = 1) THEN 0
                ELSE 1
            END AS ai_priority
        FROM reviews r
        JOIN sku s ON s.id = r.sku_id AND s.org_id = :org_id
        WHERE {where_clause}
        ORDER BY rating_priority ASC, ai_priority ASC, age_hours DESC
        LIMIT :limit
    """

    params["now"] = now

    results = []
    for row in exec_scoped(db, query, params, org_id):
        (
            review_id,
            marketplace,
            rating,
            has_media,
            ai_needed,
            created_at,
            age_hours,
            sku_id,
            article,
            external_id,
            _,
            _,
        ) = row

        # Build link if possible
        link = None
        if marketplace == "WB" and external_id:
            link = f"https://www.wildberries.ru/catalog/{external_id}/feedbacks"
        elif marketplace == "OZON" and external_id:
            link = f"https://www.ozon.ru/product/{external_id}/?tab=reviews"

        results.append(
            {
                "review_id": review_id,
                "marketplace": marketplace,
                "rating": rating,
                "has_media": bool(has_media),
                "ai_needed": bool(ai_needed),
                "created_at_utc": created_at.isoformat() if created_at else None,
                "age_hours": round(age_hours, 1),
                "sku_id": sku_id,
                "article": article,
                "external_id": external_id,
                "link": link,
            }
        )

    return results
