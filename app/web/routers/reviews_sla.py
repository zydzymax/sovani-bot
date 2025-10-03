"""Reviews SLA API endpoints (Stage 18)."""

from __future__ import annotations

import csv
import io
import logging
from datetime import timezone, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.web.deps import get_db
from app.db.utils import exec_scoped
from app.ops.escalation import notify_overdue_reviews
from app.services.reviews_sla import compute_review_sla, find_overdue_reviews
from app.web.deps import OrgScope, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reviews/sla", tags=["Reviews SLA"])


@router.get("/summary")
def get_sla_summary(
    org_id: OrgScope,
    db: Session = Depends(get_db),
    date_from: date | None = Query(None, description="Start date (default: 7 days ago)"),
    date_to: date | None = Query(None, description="End date (default: today)"),
    marketplace: str | None = Query(
        None, pattern="^(WB|OZON)$", description="Filter by marketplace"
    ),
    sku_id: int | None = Query(None, description="Filter by SKU ID"),
):
    """Get SLA summary metrics for date range.

    Returns aggregates:
        - count_total: Total reviews
        - replied: Reviews with first reply
        - within_sla: Reviews replied within SLA window
        - share_within_sla: Percentage within SLA
        - median_ttfr_min: Median time to first reply (minutes)
        - by_marketplace: Breakdown by marketplace
        - by_reply_kind: Breakdown by template vs AI
    """
    # Default to last 7 days
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=6)

    # Convert to datetime for query
    d_from_dt = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    d_to_dt = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    summary = compute_review_sla(
        db, org_id=org_id, d_from=d_from_dt, d_to=d_to_dt, marketplace=marketplace, sku_id=sku_id
    )

    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "marketplace": marketplace,
        "sku_id": sku_id,
        **summary,
    }


@router.get("/backlog")
def get_sla_backlog(
    org_id: OrgScope,
    db: Session = Depends(get_db),
    escalate_after_hours: int | None = Query(
        None, ge=1, le=72, description="Override escalation threshold"
    ),
    limit: int = Query(100, ge=1, le=500, description="Max reviews to return"),
    marketplace: str | None = Query(
        None, pattern="^(WB|OZON)$", description="Filter by marketplace"
    ),
):
    """Get list of overdue reviews (backlog).

    Returns reviews without first reply, sorted by priority:
        1. Negative (rating <=2) + ai_needed=True
        2. Negative + ai_needed=False
        3. Neutral (rating=3) + ai_needed=True
        4. Neutral + ai_needed=False
        5. Positive (rating>=4) + ai_needed=True
        6. Positive + ai_needed=False
    """
    settings = get_settings()

    escalate_hours = escalate_after_hours or settings.sla_escalate_after_hours
    now = datetime.now(timezone.utc)

    overdue = find_overdue_reviews(
        db,
        org_id=org_id,
        now=now,
        escalate_after_hours=escalate_hours,
        limit=limit,
        marketplace=marketplace,
    )

    return {
        "total": len(overdue),
        "escalate_after_hours": escalate_hours,
        "reviews": overdue,
    }


@router.post("/escalate")
def trigger_escalation(
    org_id: OrgScope,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Manually trigger SLA escalation notifications (admin only).

    Runs the escalation check immediately and sends Telegram notifications.

    Returns:
        Stats with overdue_count and messages_sent

    """
    settings = get_settings()

    now = datetime.now(timezone.utc)
    overdue = find_overdue_reviews(
        db,
        org_id=org_id,
        now=now,
        escalate_after_hours=settings.sla_escalate_after_hours,
        limit=settings.sla_backlog_limit,
    )

    if not overdue:
        return {
            "status": "ok",
            "overdue_count": 0,
            "messages_sent": 0,
            "message": "No overdue reviews",
        }

    # Parse chat IDs
    chat_ids_str = settings.sla_notify_chat_ids.strip()
    if not chat_ids_str:
        raise HTTPException(status_code=400, detail="SLA_NOTIFY_CHAT_IDS not configured")

    chat_ids = [int(cid.strip()) for cid in chat_ids_str.split(",") if cid.strip()]

    # Send notifications
    messages_sent = notify_overdue_reviews(
        overdue,
        chat_ids,
        batch_size=settings.sla_batch_size,
    )

    # Update metrics
    from app.core.metrics import reviews_escalation_sent_total, reviews_overdue_total

    reviews_overdue_total.set(len(overdue))
    reviews_escalation_sent_total.inc(messages_sent)

    return {
        "status": "ok",
        "overdue_count": len(overdue),
        "messages_sent": messages_sent,
        "message": f"Escalation sent: {len(overdue)} reviews, {messages_sent} messages",
    }


@router.get("/export/csv")
def export_sla_csv(
    org_id: OrgScope,
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    marketplace: str | None = Query(None, pattern="^(WB|OZON)$"),
):
    """Export SLA data as CSV.

    Exports data from vw_reviews_sla view with filters.
    """
    # Default to last 30 days
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=29)

    # Build query (scoped to org)
    where_clauses = ["org_id = :org_id", "created_at_utc BETWEEN :d_from AND :d_to"]
    params = {
        "org_id": org_id,
        "d_from": datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc),
        "d_to": datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc),
    }

    if marketplace:
        where_clauses.append("marketplace = :marketplace")
        params["marketplace"] = marketplace

    where_clause = " AND ".join(where_clauses)

    query = f"""
        SELECT
            review_id,
            marketplace,
            sku_id,
            article,
            created_at_utc,
            rating,
            ai_needed,
            first_reply_at_utc,
            ttfr_minutes,
            within_sla,
            reply_status,
            reply_kind
        FROM vw_reviews_sla
        WHERE {where_clause}
        ORDER BY created_at_utc DESC
        LIMIT 10000
    """

    rows = exec_scoped(db, query, params, org_id).fetchall()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "review_id",
            "marketplace",
            "sku_id",
            "article",
            "created_at_utc",
            "rating",
            "ai_needed",
            "first_reply_at_utc",
            "ttfr_minutes",
            "within_sla",
            "reply_status",
            "reply_kind",
        ]
    )

    # Data rows
    for row in rows:
        writer.writerow(row)

    output.seek(0)

    filename = f"reviews_sla_{date_from}_{date_to}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
