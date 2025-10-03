"""Tests for alert sending and deduplication."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ops.alerts import clear_alert_cache, send_alert, send_alert_with_dedup


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear alert cache before each test."""
    clear_alert_cache()
    yield
    clear_alert_cache()


def test_send_alert_success(db: Session):
    """Test successful alert sending."""
    with patch("app.ops.alerts.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.alert_chat_ids = "123456789"
            mock_settings.return_value.alert_min_severity = "warning"
            mock_settings.return_value.telegram_token = "test_token"

            result = send_alert(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="test_fp",
                extras={"key": "value"},
            )

            assert result is True
            mock_bot.send_message.assert_called_once()


def test_send_alert_below_min_severity(db: Session):
    """Test alert not sent when below minimum severity."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.alert_min_severity = "error"
        mock_settings.return_value.alert_chat_ids = "123456789"

        result = send_alert(
            db,
            source="test_detector",
            severity="warning",  # Below "error"
            message="Test alert",
            fingerprint="test_fp",
        )

        assert result is False


def test_send_alert_no_chat_ids(db: Session):
    """Test alert not sent when no chat IDs configured."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.alert_chat_ids = ""
        mock_settings.return_value.alert_min_severity = "warning"

        result = send_alert(
            db,
            source="test_detector",
            severity="error",
            message="Test alert",
            fingerprint="test_fp",
        )

        assert result is False


def test_send_alert_telegram_failure(db: Session):
    """Test alert handling when Telegram send fails."""
    with patch("app.ops.alerts.Bot") as MockBot:
        mock_bot = MagicMock()
        mock_bot.send_message.side_effect = RuntimeError("Telegram API error")
        MockBot.return_value = mock_bot

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.alert_chat_ids = "123456789"
            mock_settings.return_value.alert_min_severity = "warning"
            mock_settings.return_value.telegram_token = "test_token"

            result = send_alert(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="test_fp",
            )

            # Should return False when send fails
            assert result is False


def test_send_alert_logs_to_database(db: Session):
    """Test alert is logged to database."""
    with patch("app.ops.alerts.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.alert_chat_ids = "123456789"
            mock_settings.return_value.alert_min_severity = "warning"
            mock_settings.return_value.telegram_token = "test_token"

            send_alert(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="test_fp",
                extras={"key": "value"},
            )

            # Check database record
            result = db.execute(
                text("SELECT COUNT(*) FROM ops_alerts_history WHERE source = 'test_detector'")
            ).scalar()

            assert result >= 1


def test_send_alert_with_dedup_first_send(db: Session):
    """Test first alert is sent (not deduplicated)."""
    with patch("app.ops.alerts.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.alert_chat_ids = "123456789"
            mock_settings.return_value.alert_min_severity = "warning"
            mock_settings.return_value.telegram_token = "test_token"
            mock_settings.return_value.alert_dedup_window_sec = 300

            result = send_alert_with_dedup(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="unique_fp",
            )

            assert result is True


def test_send_alert_with_dedup_duplicate(db: Session):
    """Test duplicate alert is suppressed."""
    with patch("app.ops.alerts.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.alert_chat_ids = "123456789"
            mock_settings.return_value.alert_min_severity = "warning"
            mock_settings.return_value.telegram_token = "test_token"
            mock_settings.return_value.alert_dedup_window_sec = 300

            # Send first alert
            result1 = send_alert_with_dedup(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="unique_fp",
            )

            # Send duplicate immediately
            result2 = send_alert_with_dedup(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="unique_fp",
            )

            assert result1 is True
            assert result2 is False  # Deduplicated


def test_send_alert_with_dedup_after_window(db: Session):
    """Test alert sent after dedup window expires."""
    with patch("app.ops.alerts.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.alert_chat_ids = "123456789"
            mock_settings.return_value.alert_min_severity = "warning"
            mock_settings.return_value.telegram_token = "test_token"
            mock_settings.return_value.alert_dedup_window_sec = 1  # 1 second window

            # Send first alert
            result1 = send_alert_with_dedup(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="unique_fp",
            )

            # Wait for dedup window to expire
            import time

            time.sleep(1.1)

            # Send again after window
            result2 = send_alert_with_dedup(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="unique_fp",
            )

            assert result1 is True
            assert result2 is True  # Not deduplicated


def test_clear_alert_cache():
    """Test cache clearing."""
    from app.ops.alerts import _alert_cache

    # Add some entries to cache
    _alert_cache["fp1"] = datetime.utcnow()
    _alert_cache["fp2"] = datetime.utcnow()

    assert len(_alert_cache) == 2

    clear_alert_cache()

    assert len(_alert_cache) == 0


def test_send_alert_multiple_chat_ids(db: Session):
    """Test alert sent to multiple chat IDs."""
    with patch("app.ops.alerts.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.alert_chat_ids = "123456789,987654321,555555555"
            mock_settings.return_value.alert_min_severity = "warning"
            mock_settings.return_value.telegram_token = "test_token"

            result = send_alert(
                db,
                source="test_detector",
                severity="error",
                message="Test alert",
                fingerprint="test_fp",
            )

            assert result is True
            assert mock_bot.send_message.call_count == 3
