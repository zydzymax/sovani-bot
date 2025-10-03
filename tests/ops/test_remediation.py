"""Tests for auto-remediation actions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ops.remediation import (
    REMEDIATION_MAP,
    remediate_clear_cache,
    remediate_notify_admin,
    remediate_restart_scheduler,
    remediate_vacuum_db,
    trigger_remediation,
)


def test_remediate_clear_cache_success(db: Session):
    """Test successful cache clearing."""
    alert = {"source": "test", "msg": "test"}

    result = remediate_clear_cache(db, alert)

    assert result["status"] == "success"
    assert "cleared" in result["details"].lower()


def test_remediate_restart_scheduler_placeholder(db: Session):
    """Test scheduler restart (placeholder)."""
    alert = {"source": "test", "msg": "test"}

    result = remediate_restart_scheduler(db, alert)

    assert result["status"] == "success"
    assert "placeholder" in result["details"].lower()


def test_remediate_notify_admin_success(db: Session):
    """Test admin notification."""
    with patch("app.ops.remediation.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot

        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value.manager_chat_id = 123456789
            mock_settings.return_value.telegram_token = "test_token"

            alert = {"source": "test", "msg": "critical issue", "extras": {"key": "value"}}

            result = remediate_notify_admin(db, alert)

            assert result["status"] == "success"
            assert "notified admin" in result["details"].lower()
            mock_bot.send_message.assert_called_once()


def test_remediate_notify_admin_no_manager(db: Session):
    """Test admin notification with no manager configured."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.manager_chat_id = 0

        alert = {"source": "test", "msg": "critical issue"}

        result = remediate_notify_admin(db, alert)

        assert result["status"] == "failure"
        assert "no manager_chat_id" in result["details"].lower()


def test_remediate_vacuum_db_success(db: Session):
    """Test database vacuum."""
    alert = {"source": "test", "msg": "db too large"}

    result = remediate_vacuum_db(db, alert)

    assert result["status"] == "success"
    assert "vacuumed" in result["details"].lower()


def test_trigger_remediation_disabled(db: Session):
    """Test remediation when disabled in config."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = False

        alert = {"source": "check_api_latency_p95", "ok": False}

        result = trigger_remediation(db, alert)

        assert result["status"] == "disabled"
        assert result["action_name"] is None


def test_trigger_remediation_no_action_mapped(db: Session):
    """Test remediation for source with no action mapped."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = True

        alert = {"source": "unknown_detector", "ok": False}

        result = trigger_remediation(db, alert)

        assert result["status"] == "no_action"
        assert result["action_name"] is None


def test_trigger_remediation_success(db: Session):
    """Test successful remediation trigger."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = True
        mock_settings.return_value.auto_remediation_max_retries = 3

        alert = {"source": "check_api_latency_p95", "ok": False, "msg": "high latency"}

        result = trigger_remediation(db, alert)

        assert result["status"] == "success"
        assert result["action_name"] == "remediate_clear_cache"
        assert result["retry_count"] == 0


def test_trigger_remediation_logs_to_database(db: Session):
    """Test remediation is logged to database."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = True
        mock_settings.return_value.auto_remediation_max_retries = 3

        alert = {"source": "check_api_latency_p95", "ok": False}

        trigger_remediation(db, alert)

        # Check database record
        result = db.execute(
            text(
                "SELECT COUNT(*) FROM ops_remediation_history WHERE action_name = 'remediate_clear_cache'"
            )
        ).scalar()

        assert result >= 1


def test_trigger_remediation_with_retries(db: Session):
    """Test remediation retries on failure."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = True
        mock_settings.return_value.auto_remediation_max_retries = 2

        # Mock remediation function to fail first 2 times, succeed on 3rd
        call_count = 0

        def mock_remediate(db, alert):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Remediation failed")
            return {"status": "success", "details": "Fixed on retry"}

        with patch.object(REMEDIATION_MAP, "__getitem__", return_value=mock_remediate):
            alert = {"source": "check_api_latency_p95", "ok": False}

            result = trigger_remediation(db, alert)

            assert result["status"] == "success"
            assert result["retry_count"] == 2
            assert call_count == 3


def test_trigger_remediation_max_retries_exceeded(db: Session):
    """Test remediation fails after max retries."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = True
        mock_settings.return_value.auto_remediation_max_retries = 2

        # Mock remediation function to always fail
        def mock_remediate(db, alert):
            raise RuntimeError("Always fails")

        with patch.object(REMEDIATION_MAP, "__getitem__", return_value=mock_remediate):
            alert = {"source": "check_api_latency_p95", "ok": False}

            result = trigger_remediation(db, alert)

            assert result["status"] == "failure"
            assert "max retries exceeded" in result["details"].lower()
            assert result["retry_count"] > 0


def test_remediation_map_coverage():
    """Test that all expected detectors have remediation mapped."""
    expected_sources = [
        "check_api_latency_p95",
        "check_scheduler_on_time",
        "check_cash_balance_threshold",
        "check_db_growth",
    ]

    for source in expected_sources:
        assert source in REMEDIATION_MAP, f"Missing remediation for {source}"


def test_remediation_map_functions_callable():
    """Test that all remediation functions are callable."""
    for source, func in REMEDIATION_MAP.items():
        assert callable(func), f"Remediation for {source} is not callable"
