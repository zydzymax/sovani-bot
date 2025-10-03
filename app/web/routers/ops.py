"""Operational monitoring API endpoints (Stage 17)."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ops.detectors import run_all_detectors
from app.ops.remediation import trigger_remediation
from app.ops.slo import calculate_slo_compliance, get_slo_summary_last_n_days
from app.web.deps import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ops", tags=["Operations"])


@router.get("/health")
def get_ops_health(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get operational health summary.

    Returns metrics from vw_ops_health view.
    """
    query = text(
        """
        SELECT
            alerts_last_hour,
            critical_last_24h,
            remediations_last_hour,
            remediation_failures_24h
        FROM vw_ops_health
    """
    )
    result = db.execute(query).first()

    if not result:
        return {
            "alerts_last_hour": 0,
            "critical_last_24h": 0,
            "remediations_last_hour": 0,
            "remediation_failures_24h": 0,
        }

    return {
        "alerts_last_hour": result[0],
        "critical_last_24h": result[1],
        "remediations_last_hour": result[2],
        "remediation_failures_24h": result[3],
    }


@router.get("/alerts")
def get_recent_alerts(
    limit: int = Query(50, ge=1, le=500),
    severity: str | None = Query(None, regex="^(info|warning|error|critical)$"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get recent alerts history.

    Query params:
        limit: Max results (1-500, default 50)
        severity: Filter by severity (optional)
    """
    if severity:
        query = text(
            """
            SELECT
                id,
                created_at,
                source,
                severity,
                message,
                fingerprint,
                extras_json,
                sent_to_chat_ids
            FROM ops_alerts_history
            WHERE severity = :severity
            ORDER BY created_at DESC
            LIMIT :limit
        """
        )
        rows = db.execute(query, {"severity": severity, "limit": limit}).fetchall()
    else:
        query = text(
            """
            SELECT
                id,
                created_at,
                source,
                severity,
                message,
                fingerprint,
                extras_json,
                sent_to_chat_ids
            FROM ops_alerts_history
            ORDER BY created_at DESC
            LIMIT :limit
        """
        )
        rows = db.execute(query, {"limit": limit}).fetchall()

    return [
        {
            "id": row[0],
            "created_at": row[1].isoformat() if row[1] else None,
            "source": row[2],
            "severity": row[3],
            "message": row[4],
            "fingerprint": row[5],
            "extras_json": row[6],
            "sent_to_chat_ids": row[7],
        }
        for row in rows
    ]


@router.post("/run-detectors")
def run_detectors_endpoint(
    _admin: bool = Depends(require_admin), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Run all health check detectors (admin only).

    Returns:
        Results from all detectors with pass/fail status.

    """
    results = run_all_detectors(db)

    # Count by status
    passed = sum(1 for r in results if r.get("ok"))
    failed = len(results) - passed

    return {
        "status": "completed",
        "total_checks": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


@router.post("/remediate")
def trigger_remediation_endpoint(
    alert_source: str = Query(..., description="Detector source name"),
    _admin: bool = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Manually trigger remediation action (admin only).

    Query params:
        alert_source: Detector source (e.g., check_db_growth)
    """
    # Create mock alert for remediation
    mock_alert = {
        "source": alert_source,
        "ok": False,
        "severity": "warning",
        "msg": "Manual remediation trigger",
        "fingerprint": "manual",
        "extras": {},
    }

    result = trigger_remediation(db, mock_alert)

    if result["status"] == "disabled":
        raise HTTPException(status_code=400, detail="Auto-remediation disabled in config")

    if result["status"] == "no_action":
        raise HTTPException(status_code=404, detail=f"No remediation mapped for {alert_source}")

    return result


@router.get("/slo")
def get_slo_compliance_endpoint(
    date_from: date | None = Query(None, description="Start date (default: 7 days ago)"),
    date_to: date | None = Query(None, description="End date (default: today)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get SLO compliance report.

    Query params:
        date_from: Start date (optional, default 7 days ago)
        date_to: End date (optional, default today)
    """
    if not date_from:
        date_from = date.today() - timedelta(days=6)
    if not date_to:
        date_to = date.today()

    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")

    return calculate_slo_compliance(db, date_from, date_to)


@router.get("/slo/summary")
def get_slo_summary_endpoint(
    days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Get SLO compliance summary for last N days.

    Query params:
        days: Number of days to analyze (1-90, default 7)
    """
    return get_slo_summary_last_n_days(db, days)
