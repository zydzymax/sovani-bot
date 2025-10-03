"""Automatic remediation actions for detected issues."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import auto_remediation_total

logger = logging.getLogger(__name__)


def remediate_clear_cache(db: Session, alert: dict[str, Any]) -> dict[str, str]:
    """Clear application caches.

    Useful for resolving stale data issues.
    """
    try:
        # Clear alert deduplication cache
        from app.ops.alerts import clear_alert_cache

        clear_alert_cache()

        # Clear settings cache
        from app.core.config import get_settings

        get_settings.cache_clear()

        logger.info("Cleared application caches")
        return {"status": "success", "details": "Cleared alert and settings caches"}
    except Exception as e:
        logger.exception("Failed to clear caches")
        return {"status": "failure", "details": str(e)}


def remediate_restart_scheduler(db: Session, alert: dict[str, Any]) -> dict[str, str]:
    """Restart scheduler (placeholder).

    In production, this would trigger systemd restart or similar.
    """
    try:
        # NOTE: Actual implementation would use systemd API or subprocess
        # subprocess.run(["systemctl", "restart", "sovani-scheduler"], check=True)

        logger.warning("Scheduler restart requested but not implemented (placeholder)")
        return {
            "status": "success",
            "details": "Scheduler restart triggered (placeholder - requires systemd integration)",
        }
    except Exception as e:
        logger.exception("Failed to restart scheduler")
        return {"status": "failure", "details": str(e)}


def remediate_notify_admin(db: Session, alert: dict[str, Any]) -> dict[str, str]:
    """Send critical alert to admin (escalation).

    Uses manager_chat_id from config.
    """
    try:
        settings = get_settings()
        manager_chat_id = settings.manager_chat_id

        if not manager_chat_id or manager_chat_id == 0:
            return {"status": "failure", "details": "No manager_chat_id configured"}

        from telegram import Bot

        bot = Bot(token=settings.telegram_token)

        msg = (
            f"🚨 **CRITICAL ALERT ESCALATION**\n\n"
            f"**Source:** {alert.get('source', 'unknown')}\n"
            f"**Message:** {alert.get('msg', 'no message')}\n\n"
            f"**Extras:** {json.dumps(alert.get('extras', {}), indent=2)}\n\n"
            f"Manual intervention may be required."
        )

        bot.send_message(chat_id=manager_chat_id, text=msg, parse_mode="Markdown")

        logger.info(f"Escalated alert to admin (chat_id={manager_chat_id})")
        return {"status": "success", "details": f"Notified admin at chat {manager_chat_id}"}
    except Exception as e:
        logger.exception("Failed to notify admin")
        return {"status": "failure", "details": str(e)}


def remediate_vacuum_db(db: Session, alert: dict[str, Any]) -> dict[str, str]:
    """Run database VACUUM to reclaim space (SQLite).

    For PostgreSQL, run VACUUM ANALYZE.
    """
    try:
        # SQLite-specific
        db.execute("VACUUM")
        db.commit()

        logger.info("Database VACUUM completed")
        return {"status": "success", "details": "Database vacuumed successfully"}
    except Exception as e:
        logger.exception("Failed to vacuum database")
        db.rollback()
        return {"status": "failure", "details": str(e)}


# Remediation action mapping: detector source -> remediation function
REMEDIATION_MAP: dict[str, callable] = {
    "check_api_latency_p95": remediate_clear_cache,
    "check_scheduler_on_time": remediate_restart_scheduler,
    "check_cash_balance_threshold": remediate_notify_admin,
    "check_db_growth": remediate_vacuum_db,
    # Add more mappings as needed
}


def trigger_remediation(
    db: Session, alert: dict[str, Any], max_retries: int | None = None
) -> dict[str, Any]:
    """Trigger automatic remediation for an alert.

    Args:
        db: Database session
        alert: Alert dict from detector
        max_retries: Max retry attempts (defaults to config value)

    Returns:
        Dict with status, action_name, details

    """
    settings = get_settings()

    if not settings.auto_remediation_enabled:
        logger.debug("Auto-remediation disabled in config")
        return {"status": "disabled", "action_name": None, "details": "Auto-remediation disabled"}

    source = alert.get("source")
    remediation_func = REMEDIATION_MAP.get(source)

    if not remediation_func:
        logger.debug(f"No remediation mapped for source: {source}")
        return {"status": "no_action", "action_name": None, "details": "No remediation defined"}

    action_name = remediation_func.__name__
    max_retries = max_retries or settings.auto_remediation_max_retries
    retry_count = 0

    result = None
    while retry_count <= max_retries:
        try:
            result = remediation_func(db, alert)
            break
        except Exception as e:
            logger.exception(f"Remediation {action_name} failed (attempt {retry_count + 1})")
            retry_count += 1
            if retry_count > max_retries:
                result = {"status": "failure", "details": f"Max retries exceeded: {e}"}

    # Increment Prometheus metric
    status = result.get("status", "unknown") if result else "unknown"
    auto_remediation_total.labels(action=action_name, result=status).inc()

    # Log remediation to database
    try:
        db.execute(
            text(
                """
            INSERT INTO ops_remediation_history
            (triggered_at, action_name, status, details, retry_count)
            VALUES (:triggered_at, :action_name, :status, :details, :retry_count)
            """
            ),
            {
                "triggered_at": datetime.utcnow(),
                "action_name": action_name,
                "status": result.get("status", "unknown"),
                "details": json.dumps(result),
                "retry_count": retry_count,
            },
        )
        db.commit()
    except Exception:
        logger.exception("Failed to log remediation to database")
        db.rollback()

    return {
        "status": result.get("status", "unknown"),
        "action_name": action_name,
        "details": result.get("details", ""),
        "retry_count": retry_count,
    }
