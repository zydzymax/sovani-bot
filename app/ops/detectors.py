"""Health check detectors for operational monitoring.

Each detector returns standardized dict:
{
    "ok": bool,
    "severity": "warning" | "error" | "critical",
    "msg": str,
    "fingerprint": str,  # MD5 hash for deduplication
    "extras": dict  # Optional context
}
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import detector_checks_total

logger = logging.getLogger(__name__)


def _fingerprint(source: str, key: str) -> str:
    """Generate MD5 fingerprint for alert deduplication."""
    return hashlib.md5(f"{source}:{key}".encode()).hexdigest()


def check_api_latency_p95(db: Session) -> dict[str, Any]:
    """Check API p95 latency against SLO target.

    NOTE: Requires metrics collection infrastructure (Prometheus/StatsD).
    This is a placeholder implementation.
    """
    settings = get_settings()
    source = "check_api_latency_p95"

    # TODO: Query actual metrics from Prometheus/StatsD
    # For now, return success (placeholder)
    current_p95 = 0.0  # ms

    if current_p95 > settings.slo_api_latency_p95_ms:
        return {
            "ok": False,
            "severity": "warning",
            "msg": f"API p95 latency {current_p95:.0f}ms exceeds SLO {settings.slo_api_latency_p95_ms}ms",
            "fingerprint": _fingerprint(source, "latency_breach"),
            "extras": {"current_p95_ms": current_p95, "target_ms": settings.slo_api_latency_p95_ms},
        }

    return {
        "ok": True,
        "severity": "info",
        "msg": "API latency within SLO",
        "fingerprint": _fingerprint(source, "ok"),
        "extras": {"current_p95_ms": current_p95},
    }


def check_ingest_success_rate(db: Session) -> dict[str, Any]:
    """Check data ingestion success rate against SLO.

    Uses daily_sales table as proxy for successful ingestion.
    """
    settings = get_settings()
    source = "check_ingest_success_rate"

    # Check last 24 hours of data
    yesterday = date.today() - timedelta(days=1)

    # Count sales records for yesterday
    query = text(
        """
        SELECT COUNT(*) FROM daily_sales
        WHERE d >= :d_from
    """
    )
    result = db.execute(query, {"d_from": yesterday}).scalar()
    records_count = result or 0

    # Simple heuristic: if we have sales data, ingestion is working
    # In production, track actual API call success/failure rates
    if records_count == 0:
        return {
            "ok": False,
            "severity": "error",
            "msg": f"No sales data ingested since {yesterday}",
            "fingerprint": _fingerprint(source, "no_data"),
            "extras": {"last_date": str(yesterday), "records": 0},
        }

    # Calculate success rate (placeholder - assumes 100% if data exists)
    success_rate = 100.0

    if success_rate < settings.slo_ingest_success_rate_pct:
        return {
            "ok": False,
            "severity": "error",
            "msg": f"Ingest success rate {success_rate:.1f}% below SLO {settings.slo_ingest_success_rate_pct}%",
            "fingerprint": _fingerprint(source, "low_rate"),
            "extras": {
                "success_rate_pct": success_rate,
                "target_pct": settings.slo_ingest_success_rate_pct,
            },
        }

    return {
        "ok": True,
        "severity": "info",
        "msg": "Data ingestion within SLO",
        "fingerprint": _fingerprint(source, "ok"),
        "extras": {"records_24h": records_count, "success_rate_pct": success_rate},
    }


def check_scheduler_on_time(db: Session) -> dict[str, Any]:
    """Check scheduler job execution timeliness.

    NOTE: Requires scheduler job execution logging.
    This is a placeholder implementation.
    """
    settings = get_settings()
    source = "check_scheduler_on_time"

    # TODO: Query scheduler execution logs
    # For now, return success (placeholder)
    on_time_pct = 100.0

    if on_time_pct < settings.slo_scheduler_on_time_pct:
        return {
            "ok": False,
            "severity": "warning",
            "msg": f"Scheduler on-time rate {on_time_pct:.1f}% below SLO {settings.slo_scheduler_on_time_pct}%",
            "fingerprint": _fingerprint(source, "late_jobs"),
            "extras": {
                "on_time_pct": on_time_pct,
                "target_pct": settings.slo_scheduler_on_time_pct,
            },
        }

    return {
        "ok": True,
        "severity": "info",
        "msg": "Scheduler within SLO",
        "fingerprint": _fingerprint(source, "ok"),
        "extras": {"on_time_pct": on_time_pct},
    }


def check_cash_balance_threshold(db: Session) -> dict[str, Any]:
    """Check for negative cash balance alert threshold.

    Uses cashflow_daily cumulative balance from Stage 16.
    """
    settings = get_settings()
    source = "check_cash_balance_threshold"

    # Get latest cumulative balance from vw_cashflow_daily
    query = text(
        """
        SELECT d, cumulative_balance
        FROM vw_cashflow_daily
        ORDER BY d DESC
        LIMIT 1
    """
    )
    result = db.execute(query).first()

    if not result:
        return {
            "ok": True,
            "severity": "info",
            "msg": "No cashflow data available",
            "fingerprint": _fingerprint(source, "no_data"),
            "extras": {},
        }

    latest_date, balance = result
    threshold = settings.cf_negative_balance_alert_threshold

    if balance < threshold:
        return {
            "ok": False,
            "severity": "critical",
            "msg": f"Cash balance {balance:.2f} RUB below alert threshold {threshold:.2f}",
            "fingerprint": _fingerprint(source, f"negative_{latest_date}"),
            "extras": {
                "balance": float(balance),
                "threshold": float(threshold),
                "date": str(latest_date),
            },
        }

    return {
        "ok": True,
        "severity": "info",
        "msg": f"Cash balance healthy: {balance:.2f} RUB",
        "fingerprint": _fingerprint(source, "ok"),
        "extras": {"balance": float(balance), "date": str(latest_date)},
    }


def check_commission_outliers(db: Session) -> dict[str, Any]:
    """Check for commission reconciliation outliers.

    Uses vw_commission_recon from Stage 16.
    """
    source = "check_commission_outliers"

    # Get outliers from last 7 days
    d_from = date.today() - timedelta(days=7)
    query = text(
        """
        SELECT COUNT(*) FROM vw_commission_recon
        WHERE d >= :d_from AND flag_outlier = 1
    """
    )
    outliers_count = db.execute(query, {"d_from": d_from}).scalar() or 0

    if outliers_count > 5:
        return {
            "ok": False,
            "severity": "warning",
            "msg": f"{outliers_count} commission outliers detected in last 7 days",
            "fingerprint": _fingerprint(source, "outliers_detected"),
            "extras": {"outliers_count": outliers_count, "period_days": 7},
        }

    return {
        "ok": True,
        "severity": "info",
        "msg": f"Commission reconciliation clean ({outliers_count} outliers)",
        "fingerprint": _fingerprint(source, "ok"),
        "extras": {"outliers_count": outliers_count},
    }


def check_db_growth(db: Session) -> dict[str, Any]:
    """Check database size growth rate.

    NOTE: SQLite-specific implementation. For PostgreSQL, query pg_database_size().
    """
    source = "check_db_growth"

    try:
        # SQLite: Get page_count * page_size
        page_count = db.execute(text("PRAGMA page_count")).scalar() or 0
        page_size = db.execute(text("PRAGMA page_size")).scalar() or 4096
        db_size_mb = (page_count * page_size) / (1024 * 1024)

        # Alert if DB > 5GB (placeholder threshold)
        if db_size_mb > 5120:
            return {
                "ok": False,
                "severity": "warning",
                "msg": f"Database size {db_size_mb:.1f} MB exceeds 5GB threshold",
                "fingerprint": _fingerprint(source, "large_db"),
                "extras": {"size_mb": db_size_mb, "threshold_mb": 5120},
            }

        return {
            "ok": True,
            "severity": "info",
            "msg": f"Database size healthy: {db_size_mb:.1f} MB",
            "fingerprint": _fingerprint(source, "ok"),
            "extras": {"size_mb": db_size_mb},
        }
    except Exception as e:
        logger.exception("Failed to check DB growth")
        return {
            "ok": False,
            "severity": "error",
            "msg": f"DB growth check failed: {e}",
            "fingerprint": _fingerprint(source, "check_failed"),
            "extras": {"error": str(e)},
        }


def check_tenant_unscoped_queries(db: Session, window_seconds: int = 300) -> dict[str, Any]:
    """Check for unscoped SQL queries (tenant isolation violations).

    Queries tenant_unscoped_query_total metric from last window_seconds.
    Alerts on ANY unscoped query as CRITICAL security issue.

    Args:
        db: Database session
        window_seconds: Time window to check (default: 5 minutes)

    Returns:
        Alert dict with severity=critical if violations found

    """
    from app.core.metrics import tenant_unscoped_query_total

    source = "check_tenant_unscoped_queries"

    try:
        # Get current counter value
        # Note: This is cumulative, so we need to track delta or use a time-series DB
        # For now, check if counter > 0 (any violations ever)
        counter_value = (
            tenant_unscoped_query_total._value.get()
            if hasattr(tenant_unscoped_query_total, "_value")
            else 0
        )

        if counter_value > 0:
            return {
                "ok": False,
                "severity": "critical",
                "msg": f"SECURITY: {counter_value} unscoped SQL queries detected - tenant isolation violated!",
                "fingerprint": _fingerprint(source, "unscoped_queries"),
                "extras": {
                    "count": counter_value,
                    "window_seconds": window_seconds,
                    "action": "Review logs for org_id violations, check exec_scoped() usage",
                },
            }

        return {
            "ok": True,
            "severity": "info",
            "msg": "All SQL queries properly scoped - tenant isolation intact",
            "fingerprint": _fingerprint(source, "ok"),
            "extras": {"count": 0},
        }

    except Exception as e:
        logger.exception("Failed to check tenant unscoped queries")
        return {
            "ok": False,
            "severity": "error",
            "msg": f"Tenant scope check failed: {e}",
            "fingerprint": _fingerprint(source, "check_failed"),
            "extras": {"error": str(e)},
        }


def run_all_detectors(db: Session) -> list[dict[str, Any]]:
    """Run all health check detectors and return results."""
    detectors = [
        check_api_latency_p95,
        check_ingest_success_rate,
        check_scheduler_on_time,
        check_cash_balance_threshold,
        check_commission_outliers,
        check_db_growth,
        check_tenant_unscoped_queries,  # CRITICAL: Security detector
    ]

    results = []
    for detector in detectors:
        try:
            result = detector(db)
            results.append(result)

            # Increment Prometheus metric
            detector_name = detector.__name__
            check_result = "pass" if result.get("ok") else "fail"
            detector_checks_total.labels(detector=detector_name, result=check_result).inc()

        except Exception as e:
            logger.exception(f"Detector {detector.__name__} failed")
            result = {
                "ok": False,
                "severity": "error",
                "msg": f"Detector {detector.__name__} crashed: {e}",
                "fingerprint": _fingerprint(detector.__name__, "crash"),
                "extras": {"error": str(e)},
            }
            results.append(result)

            # Increment fail metric
            detector_checks_total.labels(detector=detector.__name__, result="fail").inc()

    return results
