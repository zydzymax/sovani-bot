"""SLO (Service Level Objective) compliance calculation."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def calculate_slo_compliance(db: Session, d_from: date, d_to: date) -> dict[str, Any]:
    """Calculate SLO compliance for date range.

    Returns:
        Dict with per-SLO compliance status and overall pass/fail.

    """
    settings = get_settings()

    # Query vw_slo_daily for date range
    query = text(
        """
        SELECT
            d,
            ingest_success_rate_pct,
            scheduler_on_time_pct,
            api_latency_p95_ms
        FROM vw_slo_daily
        WHERE d BETWEEN :d_from AND :d_to
        ORDER BY d
    """
    )
    rows = db.execute(query, {"d_from": d_from, "d_to": d_to}).fetchall()

    if not rows:
        return {
            "status": "no_data",
            "d_from": str(d_from),
            "d_to": str(d_to),
            "ingest": {"pass": False, "reason": "no data"},
            "scheduler": {"pass": False, "reason": "no data"},
            "api_latency": {"pass": False, "reason": "no data"},
            "overall_pass": False,
        }

    # Calculate averages
    ingest_rates = [row[1] for row in rows]
    scheduler_rates = [row[2] for row in rows]
    api_latencies = [row[3] for row in rows]

    avg_ingest = sum(ingest_rates) / len(ingest_rates)
    avg_scheduler = sum(scheduler_rates) / len(scheduler_rates)
    avg_api_latency = sum(api_latencies) / len(api_latencies)

    # Compare against targets
    ingest_pass = avg_ingest >= settings.slo_ingest_success_rate_pct
    scheduler_pass = avg_scheduler >= settings.slo_scheduler_on_time_pct
    api_latency_pass = avg_api_latency <= settings.slo_api_latency_p95_ms

    overall_pass = ingest_pass and scheduler_pass and api_latency_pass

    return {
        "status": "ok",
        "d_from": str(d_from),
        "d_to": str(d_to),
        "days_analyzed": len(rows),
        "ingest": {
            "pass": ingest_pass,
            "actual_pct": round(avg_ingest, 2),
            "target_pct": settings.slo_ingest_success_rate_pct,
        },
        "scheduler": {
            "pass": scheduler_pass,
            "actual_pct": round(avg_scheduler, 2),
            "target_pct": settings.slo_scheduler_on_time_pct,
        },
        "api_latency": {
            "pass": api_latency_pass,
            "actual_p95_ms": round(avg_api_latency, 2),
            "target_p95_ms": settings.slo_api_latency_p95_ms,
        },
        "overall_pass": overall_pass,
    }


def get_slo_summary_last_n_days(db: Session, days: int = 7) -> dict[str, Any]:
    """Get SLO compliance summary for last N days.

    Convenience wrapper around calculate_slo_compliance.
    """
    d_to = date.today()
    d_from = d_to - timedelta(days=days - 1)

    return calculate_slo_compliance(db, d_from, d_to)
