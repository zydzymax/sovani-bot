"""Scheduled jobs for nightly data collection and processing.

Jobs:
- collect_yesterday_data: Collect WB/Ozon data for yesterday
- recalc_recent_metrics: Recalculate metrics for last 35 days (rolling window)

All jobs are idempotent and can be run multiple times safely.
"""

from __future__ import annotations

from datetime import timezone, date, timedelta

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.ops.alerts import send_alert_with_dedup
from app.ops.detectors import run_all_detectors
from app.ops.escalation import notify_overdue_reviews
from app.ops.remediation import trigger_remediation
from app.services.ingestion import collect_wb_sales_stub
from app.services.recalc_metrics import recalc_metrics_for_date
from app.services.reviews_sla import find_overdue_reviews

log = get_logger("sovani_bot.scheduler")


def collect_yesterday_data() -> dict[str, int]:
    """Collect data for yesterday from all sources.

    This job should run nightly (e.g., at 02:00 UTC).

    Returns:
        Dict with collection stats (wb_sales, wb_stock, ozon_sales, etc.)

    """
    yesterday = date.today() - timedelta(days=1)

    log.info("nightly_collection_started", extra={"date": str(yesterday)})

    stats = {}

    with SessionLocal() as db:
        # Collect WB sales (stub for Stage 7)
        wb_sales = collect_wb_sales_stub(db, yesterday, yesterday)
        stats["wb_sales"] = wb_sales

        # TODO Stage 8: Add real collection calls
        # stats["wb_stock"] = collect_wb_stock(db, yesterday)
        # stats["ozon_sales"] = collect_ozon_sales(db, yesterday, yesterday)
        # stats["ozon_stock"] = collect_ozon_stock(db, yesterday)
        # stats["ozon_cashflows"] = collect_ozon_cashflows(db, yesterday, yesterday)

    log.info("nightly_collection_completed", extra={"date": str(yesterday), "stats": stats})

    return stats


def recalc_recent_metrics(days: int = 35) -> dict[str, int]:
    """Recalculate metrics for last N days (rolling window).

    This handles late-arriving data (refunds, adjustments) by recalculating
    a sliding window of recent days.

    Args:
        days: Number of days to recalculate (default 35 for ~5 weeks)

    Returns:
        Dict with processing stats per day

    """
    today = date.today()
    start_date = today - timedelta(days=days - 1)

    log.info(
        "metrics_recalc_batch_started",
        extra={"from": str(start_date), "to": str(today), "days": days},
    )

    stats = {}

    with SessionLocal() as db:
        current_date = start_date
        while current_date <= today:
            try:
                sku_count = recalc_metrics_for_date(db, current_date)
                stats[str(current_date)] = sku_count
            except Exception as e:
                log.error(
                    "metrics_recalc_failed",
                    extra={"date": str(current_date), "error": str(e)},
                )
                stats[str(current_date)] = -1  # Mark as failed

            current_date += timedelta(days=1)

    log.info("metrics_recalc_batch_completed", extra={"stats": stats, "days": days})

    return stats


def ops_health_check() -> dict[str, int]:
    """Run operational health checks and send alerts (Stage 17).

    This job should run frequently (e.g., every 5 minutes).

    Returns:
        Dict with detector stats (total, passed, failed, alerts_sent, remediations_triggered)

    """
    log.info("ops_health_check_started")

    settings = get_settings()
    stats = {"total": 0, "passed": 0, "failed": 0, "alerts_sent": 0, "remediations_triggered": 0}

    with SessionLocal() as db:
        # Run all detectors
        results = run_all_detectors(db)
        stats["total"] = len(results)

        for result in results:
            if result.get("ok"):
                stats["passed"] += 1
            else:
                stats["failed"] += 1

                # Send alert with deduplication
                try:
                    sent = send_alert_with_dedup(
                        db,
                        source=result.get("source", "unknown"),
                        severity=result.get("severity", "warning"),
                        message=result.get("msg", "No message"),
                        fingerprint=result.get("fingerprint", "unknown"),
                        extras=result.get("extras"),
                    )
                    if sent:
                        stats["alerts_sent"] += 1
                except Exception as e:
                    log.error(
                        "alert_send_failed",
                        extra={"source": result.get("source"), "error": str(e)},
                    )

                # Trigger auto-remediation if enabled
                if settings.auto_remediation_enabled:
                    try:
                        remediation_result = trigger_remediation(db, result)
                        if remediation_result.get("status") not in ["disabled", "no_action"]:
                            stats["remediations_triggered"] += 1
                    except Exception as e:
                        log.error(
                            "remediation_failed",
                            extra={"source": result.get("source"), "error": str(e)},
                        )

    log.info("ops_health_check_completed", extra={"stats": stats})

    return stats


# TODO Stage 8: Add scheduler integration
# - APScheduler / Celery Beat
# - Cron-like scheduling (nightly at 02:00 UTC)
# - Error handling and alerting (Telegram notifications)
#
# Stage 17: ops_health_check should run every 5 minutes

# Example APScheduler setup (for reference):
#
# from apscheduler.schedulers.background import BackgroundScheduler
#
# scheduler = BackgroundScheduler()
# scheduler.add_job(
#     collect_yesterday_data,
#     trigger='cron',
#     hour=2,  # 02:00 UTC
#     minute=0,
#     id='nightly_collection'
# )
# scheduler.add_job(
#     recalc_recent_metrics,
#     trigger='cron',
#     hour=3,  # 03:00 UTC (after collection)
#     minute=0,
#     id='nightly_metrics'
# )
# scheduler.start()


def reviews_sla_monitor() -> dict[str, int]:
    """Monitor reviews SLA and send escalation notifications (Stage 18).

    Runs every 30 minutes to check for overdue reviews.

    Returns:
        Dict with stats (overdue_count, messages_sent)

    """
    from datetime import datetime

    log.info("reviews_sla_monitor_started")

    settings = get_settings()
    stats = {"overdue_count": 0, "messages_sent": 0}

    with SessionLocal() as db:
        # Find overdue reviews
        now = datetime.now(timezone.utc)
        overdue = find_overdue_reviews(
            db,
            now=now,
            escalate_after_hours=settings.sla_escalate_after_hours,
            limit=settings.sla_backlog_limit,
        )

        stats["overdue_count"] = len(overdue)

        if overdue:
            # Parse chat IDs from config
            chat_ids_str = settings.sla_notify_chat_ids.strip()
            if chat_ids_str:
                chat_ids = [int(cid.strip()) for cid in chat_ids_str.split(",") if cid.strip()]

                # Send escalation notifications
                messages_sent = notify_overdue_reviews(
                    overdue,
                    chat_ids,
                    batch_size=settings.sla_batch_size,
                )

                stats["messages_sent"] = messages_sent

                # Update Prometheus metrics
                from app.core.metrics import reviews_escalation_sent_total, reviews_overdue_total

                reviews_overdue_total.set(len(overdue))
                reviews_escalation_sent_total.inc(messages_sent)
            else:
                log.warning("SLA_NOTIFY_CHAT_IDS not configured, skipping escalation")

    log.info("reviews_sla_monitor_completed", extra={"stats": stats})

    return stats


# Example APScheduler configuration (for reference):
# scheduler.add_job(
#     reviews_sla_monitor,
#     trigger='interval',
#     minutes=30,  # Every 30 minutes
#     id='reviews_sla_monitor'
# )
