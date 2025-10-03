"""Logging configuration with rotation and structured output."""

from __future__ import annotations

import logging
import logging.handlers
import os
from datetime import timezone, datetime
from pathlib import Path

from app.core.config import get_settings


def setup_logging():
    """Configure application logging with rotation.

    Sets up:
    - Console output (stdout) with INFO level
    - File output with rotation (alerts.log)
    - JSON formatter for structured logging (optional)

    """
    settings = get_settings()

    # Create logs directory if it doesn't exist
    log_dir = Path("/var/log/sovani-bot")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # Rotating file handler for alerts
    alerts_log_file = log_dir / "alerts.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=alerts_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.WARNING)  # Only warnings and errors
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    # Optional: JSON file handler for structured logging
    json_log_file = log_dir / "sovani.jsonl"
    if os.environ.get("ENABLE_JSON_LOGGING", "false").lower() == "true":
        json_handler = logging.handlers.RotatingFileHandler(
            filename=json_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.info("Logging configured successfully")


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record

        Returns:
            JSON string

        """
        import json

        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        return json.dumps(log_data, ensure_ascii=False)


def cleanup_old_logs(max_age_days: int = 30):
    """Clean up log files older than specified days.

    Args:
        max_age_days: Maximum age of log files in days

    """
    import time

    log_dir = Path("/var/log/sovani-bot")
    if not log_dir.exists():
        return

    current_time = time.time()
    max_age_seconds = max_age_days * 86400

    for log_file in log_dir.glob("*.log*"):
        if log_file.is_file():
            file_age = current_time - log_file.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    log_file.unlink()
                    logging.info(f"Deleted old log file: {log_file}")
                except Exception as e:
                    logging.error(f"Failed to delete log file {log_file}: {e}")


def cleanup_old_database_backups(max_backups: int = 10):
    """Clean up old database backups, keeping only the most recent.

    Args:
        max_backups: Maximum number of backups to keep

    """
    backup_dir = Path("/root/sovani_bot/backups")
    if not backup_dir.exists():
        return

    # Get all backup files sorted by modification time (newest first)
    backups = sorted(
        backup_dir.glob("sovani_bot_*.db"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    # Delete old backups beyond max_backups
    for backup in backups[max_backups:]:
        try:
            backup.unlink()
            logging.info(f"Deleted old database backup: {backup}")
        except Exception as e:
            logging.error(f"Failed to delete backup {backup}: {e}")
