"""Alert service for Telegram notifications."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum

import psutil
from aiogram import Bot

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "ℹ️ INFO"
    WARNING = "⚠️ WARNING"
    ERROR = "❌ ERROR"
    CRITICAL = "🚨 CRITICAL"


class AlertService:
    """Service for sending alerts to Telegram."""

    def __init__(self):
        """Initialize alert service with bot instance."""
        settings = get_settings()
        self.bot = Bot(token=settings.telegram_token)
        self.manager_chat_id = settings.manager_chat_id
        self.alert_threshold_disk = getattr(settings, "alert_threshold_disk", 90)
        self.alert_threshold_memory = getattr(settings, "alert_threshold_memory", 90)

    async def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        component: str | None = None,
    ):
        """Send alert message to manager via Telegram.

        Args:
            message: Alert message text
            level: Alert severity level
            component: Optional component name (e.g., "scheduler", "api", "db")

        """
        if not self.manager_chat_id:
            logger.warning("Manager chat ID not configured, skipping alert")
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Format alert message
        alert_text = f"{level.value}\n"
        if component:
            alert_text += f"Component: {component}\n"
        alert_text += f"Time: {timestamp}\n\n"
        alert_text += message

        try:
            await self.bot.send_message(
                chat_id=self.manager_chat_id, text=alert_text, parse_mode=None
            )
            logger.info(f"Alert sent: {level.value} - {message[:50]}")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    async def alert_job_failed(self, job_name: str, error: str):
        """Alert when scheduled job fails.

        Args:
            job_name: Name of the failed job
            error: Error message

        """
        message = f"Job '{job_name}' failed:\n{error[:300]}"
        await self.send_alert(message, level=AlertLevel.ERROR, component="scheduler")

    async def alert_api_error(self, endpoint: str, error: str):
        """Alert when API endpoint throws error.

        Args:
            endpoint: API endpoint path
            error: Error message

        """
        message = f"API error on {endpoint}:\n{error[:300]}"
        await self.send_alert(message, level=AlertLevel.ERROR, component="api")

    async def alert_disk_space_low(self):
        """Alert when disk space is low."""
        disk = psutil.disk_usage("/")
        message = (
            f"Disk space low!\n"
            f"Used: {disk.percent}%\n"
            f"Free: {round(disk.free / (1024**3), 2)} GB"
        )
        await self.send_alert(message, level=AlertLevel.WARNING, component="system")

    async def alert_memory_high(self):
        """Alert when memory usage is high."""
        mem = psutil.virtual_memory()
        message = (
            f"Memory usage high!\n"
            f"Used: {mem.percent}%\n"
            f"Available: {round(mem.available / (1024**2), 2)} MB"
        )
        await self.send_alert(message, level=AlertLevel.WARNING, component="system")

    async def alert_database_error(self, error: str):
        """Alert when database connection fails.

        Args:
            error: Error message

        """
        message = f"Database error:\n{error[:300]}"
        await self.send_alert(message, level=AlertLevel.CRITICAL, component="database")

    def check_system_resources(self) -> list[str]:
        """Check system resources and return list of warnings.

        Returns:
            List of warning messages

        """
        warnings = []

        # Check disk space
        disk = psutil.disk_usage("/")
        if disk.percent > self.alert_threshold_disk:
            warnings.append(
                f"Disk space: {disk.percent}% used (threshold: {self.alert_threshold_disk}%)"
            )

        # Check memory
        mem = psutil.virtual_memory()
        if mem.percent > self.alert_threshold_memory:
            warnings.append(
                f"Memory: {mem.percent}% used (threshold: {self.alert_threshold_memory}%)"
            )

        return warnings

    async def close(self):
        """Close bot session."""
        await self.bot.session.close()


# Singleton instance
_alert_service: AlertService | None = None


def get_alert_service() -> AlertService:
    """Get or create alert service instance."""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service


# Convenience functions for sync contexts
def send_alert_sync(
    message: str, level: AlertLevel = AlertLevel.INFO, component: str | None = None
):
    """Send alert from synchronous context.

    Args:
        message: Alert message
        level: Alert severity
        component: Component name

    """
    service = get_alert_service()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create task if loop is already running
            asyncio.create_task(service.send_alert(message, level, component))
        else:
            # Run in new loop if not running
            loop.run_until_complete(service.send_alert(message, level, component))
    except Exception as e:
        logger.error(f"Failed to send alert (sync): {e}")
