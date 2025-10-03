"""Alert sending with deduplication and Telegram integration."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session
from telegram import Bot

from app.core.config import get_settings
from app.core.metrics import alerts_deduplicated_total, alerts_total

logger = logging.getLogger(__name__)

# In-memory deduplication cache: fingerprint -> last_sent_timestamp
_alert_cache: dict[str, datetime] = {}


def send_alert(
    db: Session,
    source: str,
    severity: str,
    message: str,
    fingerprint: str,
    extras: dict[str, Any] | None = None,
) -> bool:
    """Send alert to configured Telegram chat IDs.

    Returns:
        True if alert was sent successfully, False otherwise.

    """
    settings = get_settings()

    # Check minimum severity
    severity_order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
    min_severity = settings.alert_min_severity.lower()

    if severity_order.get(severity.lower(), 0) < severity_order.get(min_severity, 1):
        logger.debug(f"Alert {source} severity {severity} below minimum {min_severity}, skipping")
        return False

    # Get chat IDs
    chat_ids_str = settings.alert_chat_ids.strip()
    if not chat_ids_str:
        logger.warning("No alert_chat_ids configured, cannot send alert")
        return False

    chat_ids = [cid.strip() for cid in chat_ids_str.split(",") if cid.strip()]

    # Format alert message
    emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}.get(
        severity.lower(), "•"
    )

    alert_text = f"{emoji} **{severity.upper()}** | {source}\n\n{message}"

    if extras:
        extras_str = "\n".join(f"  • {k}: {v}" for k, v in extras.items())
        alert_text += f"\n\n**Details:**\n{extras_str}"

    # Send to Telegram
    bot = Bot(token=settings.telegram_token)
    sent_count = 0

    for chat_id in chat_ids:
        try:
            bot.send_message(chat_id=chat_id, text=alert_text, parse_mode="Markdown")
            sent_count += 1
        except Exception as e:
            logger.exception(f"Failed to send alert to chat {chat_id}: {e}")

    # Increment Prometheus metric
    if sent_count > 0:
        alerts_total.labels(source=source, severity=severity).inc()

    # Log to database
    try:
        db.execute(
            text(
                """
            INSERT INTO ops_alerts_history
            (created_at, source, severity, message, fingerprint, extras_json, sent_to_chat_ids)
            VALUES (:created_at, :source, :severity, :message, :fingerprint, :extras_json, :sent_to_chat_ids)
            """
            ),
            {
                "created_at": datetime.utcnow(),
                "source": source,
                "severity": severity,
                "message": message,
                "fingerprint": fingerprint,
                "extras_json": json.dumps(extras) if extras else None,
                "sent_to_chat_ids": chat_ids_str,
            },
        )
        db.commit()
    except Exception as e:
        logger.exception(f"Failed to log alert to database: {e}")
        db.rollback()

    return sent_count > 0


def send_alert_with_dedup(
    db: Session,
    source: str,
    severity: str,
    message: str,
    fingerprint: str,
    extras: dict[str, Any] | None = None,
) -> bool:
    """Send alert with deduplication.

    Uses in-memory cache to prevent duplicate alerts within configured window.

    Returns:
        True if alert was sent, False if deduplicated.

    """
    settings = get_settings()
    dedup_window = timedelta(seconds=settings.alert_dedup_window_sec)

    # Check deduplication cache
    now = datetime.utcnow()
    last_sent = _alert_cache.get(fingerprint)

    if last_sent and (now - last_sent) < dedup_window:
        logger.debug(
            f"Alert {source} deduplicated (last sent {(now - last_sent).total_seconds():.0f}s ago)"
        )
        # Increment dedup metric
        alerts_deduplicated_total.labels(source=source).inc()
        return False

    # Send alert
    success = send_alert(db, source, severity, message, fingerprint, extras)

    if success:
        _alert_cache[fingerprint] = now

        # Clean old entries from cache (keep last 1000)
        if len(_alert_cache) > 1000:
            # Remove entries older than 2x dedup window
            cutoff = now - (dedup_window * 2)
            _alert_cache.clear()
            # In production, use proper LRU cache or Redis

    return success


def clear_alert_cache() -> None:
    """Clear alert deduplication cache.

    Useful for testing or manual override.
    """
    _alert_cache.clear()
    logger.info("Alert cache cleared")
