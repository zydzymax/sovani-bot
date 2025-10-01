"""Scheduled jobs for nightly data collection and processing.

Jobs:
- collect_yesterday_data: Collect WB/Ozon data for yesterday
- recalc_recent_metrics: Recalculate metrics for last 35 days (rolling window)

All jobs are idempotent and can be run multiple times safely.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.ingestion import collect_wb_sales_stub
from app.services.recalc_metrics import recalc_metrics_for_date

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


# TODO Stage 8: Add scheduler integration
# - APScheduler / Celery Beat
# - Cron-like scheduling (nightly at 02:00 UTC)
# - Error handling and alerting (Telegram notifications)

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
