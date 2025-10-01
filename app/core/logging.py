"""Structured JSON logging with secret masking and request correlation.

Provides JSON-formatted logs with automatic secret masking and request ID tracking.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from logging.handlers import RotatingFileHandler
from typing import Any

# Request correlation (cross-cutting request_id)
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(value: str | None = None) -> str:
    """Set current request_id (or generate new). Returns active id."""
    rid = value or str(uuid.uuid4())
    _request_id.set(rid)
    return rid


def get_request_id() -> str:
    """Get current request_id for contextual logging."""
    return _request_id.get()


# --- Secret masking patterns ---
_PATTERNS = [
    # OpenAI: sk-...
    (re.compile(r"\bsk-[A-Za-z0-9]{8,}\b"), "sk-***"),
    # Telegram bot token: 10 digits : token
    (re.compile(r"\b\d{9,11}:[A-Za-z0-9_-]{20,}\b"), "***:***"),
    # WB/Ozon JWT tokens and API keys (long hashes/base64/hex)
    (re.compile(r"\beyJhbGciOi[A-Za-z0-9+/=_-]{20,}\b"), "eyJ***"),
    (re.compile(r"\b[A-Za-z0-9+/=_-]{32,}\b"), "***"),
    # Bearer tokens
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{10,}\b"), "Bearer ***"),
]

_SENSITIVE_KEYS = {
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "x-api-key",
    "api_key",
    "api-key",
    "apikey",
    "wb_token",
    "ozon_token",
    "openai_api_key",
    "chatgpt_api_key",
    "telegram_token",
    "client_secret",
    "password",
    "secret",
}


def _mask_value(v: Any) -> Any:
    """Recursively mask sensitive data in any structure."""
    if v is None:
        return v
    if isinstance(v, (int, float, bool)):
        return v
    if is_dataclass(v):
        v = asdict(v)
    if isinstance(v, Mapping):
        return {
            k: ("***" if str(k).lower() in _SENSITIVE_KEYS else _mask_value(val))
            for k, val in v.items()
        }
    if isinstance(v, (list, tuple, set)):
        t = type(v)
        return t(_mask_value(i) for i in v)
    s = str(v)
    for rx, repl in _PATTERNS:
        s = rx.sub(repl, s)
    return s


class JsonFormatter(logging.Formatter):
    """JSON log formatter with automatic secret masking."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with masked secrets."""
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int((record.created - int(record.created)) * 1000):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": _mask_value(record.getMessage()),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "request_id": get_request_id() or None,
        }

        # Collect extra/context
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            )
        }
        if extras:
            payload["extra"] = _mask_value(extras)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _ensure_dir(path: str) -> None:
    """Ensure directory exists for log file."""
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def setup_logging(
    level: str | int = "INFO",
    to_stdout: bool = True,
    file_path: str | None = "/var/log/sovani-bot/bot.jsonl",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Initialize structured JSON logging.

    Args:
        level: Log level (INFO, DEBUG, WARNING, ERROR)
        to_stdout: Enable stdout logging (for systemd/journalctl)
        file_path: Path to JSON log file (None to disable file logging)
        max_bytes: Max log file size before rotation (default: 5MB)
        backup_count: Number of backup files to keep (default: 5)

    Features:
        - JSON structured logs
        - Automatic secret masking
        - Log rotation
        - Request ID correlation

    """
    root = logging.getLogger()
    root.setLevel(logging.getLevelName(level) if isinstance(level, str) else level)

    # Remove old handlers to avoid duplicates
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = JsonFormatter()

    if to_stdout:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    if file_path:
        _ensure_dir(file_path)
        fh = RotatingFileHandler(
            file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance by name."""
    return logging.getLogger(name)


__all__ = [
    "setup_logging",
    "get_logger",
    "set_request_id",
    "get_request_id",
    "JsonFormatter",
]
