"""Tests for operations API endpoints."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.web.main import app

client = TestClient(app)


@pytest.fixture
def admin_headers():
    """Mock admin authentication headers."""
    with patch("app.web.deps.require_admin", return_value=True):
        yield {"Authorization": "Bearer fake_admin_token"}


def test_get_ops_health(db: Session):
    """Test GET /api/v1/ops/health."""
    response = client.get("/api/v1/ops/health")

    assert response.status_code == 200
    data = response.json()

    assert "alerts_last_hour" in data
    assert "critical_last_24h" in data
    assert "remediations_last_hour" in data
    assert "remediation_failures_24h" in data


def test_get_recent_alerts_default(db: Session):
    """Test GET /api/v1/ops/alerts with defaults."""
    response = client.get("/api/v1/ops/alerts")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)


def test_get_recent_alerts_with_limit(db: Session):
    """Test GET /api/v1/ops/alerts with custom limit."""
    # Insert test alerts
    for i in range(10):
        db.execute(
            text(
                """
            INSERT INTO ops_alerts_history
            (created_at, source, severity, message, fingerprint)
            VALUES (datetime('now'), :source, 'warning', 'Test alert', :fp)
            """
            ),
            {"source": f"test_{i}", "fp": f"fp_{i}"},
        )
    db.commit()

    response = client.get("/api/v1/ops/alerts?limit=5")

    assert response.status_code == 200
    data = response.json()

    assert len(data) <= 5


def test_get_recent_alerts_filter_by_severity(db: Session):
    """Test GET /api/v1/ops/alerts filtered by severity."""
    # Insert mixed severity alerts
    db.execute(
        text(
            """
        INSERT INTO ops_alerts_history
        (created_at, source, severity, message, fingerprint)
        VALUES
        (datetime('now'), 'test1', 'critical', 'Critical alert', 'fp1'),
        (datetime('now'), 'test2', 'warning', 'Warning alert', 'fp2')
        """
        )
    )
    db.commit()

    response = client.get("/api/v1/ops/alerts?severity=critical")

    assert response.status_code == 200
    data = response.json()

    # All returned alerts should be critical
    for alert in data:
        if alert["source"].startswith("test"):
            assert alert["severity"] == "critical"


def test_run_detectors_endpoint(db: Session, admin_headers):
    """Test POST /api/v1/ops/run-detectors (admin only)."""
    response = client.post("/api/v1/ops/run-detectors", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert "total_checks" in data
    assert "passed" in data
    assert "failed" in data
    assert "results" in data

    # Should run 6 detectors
    assert data["total_checks"] == 6


def test_run_detectors_endpoint_requires_admin(db: Session):
    """Test POST /api/v1/ops/run-detectors requires admin."""
    # Without admin headers, should fail
    response = client.post("/api/v1/ops/run-detectors")

    # Will fail due to missing authentication
    assert response.status_code != 200


def test_trigger_remediation_endpoint(db: Session, admin_headers):
    """Test POST /api/v1/ops/remediate (admin only)."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = True

        response = client.post(
            "/api/v1/ops/remediate?alert_source=check_api_latency_p95",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "action_name" in data


def test_trigger_remediation_disabled(db: Session, admin_headers):
    """Test POST /api/v1/ops/remediate when disabled."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = False

        response = client.post(
            "/api/v1/ops/remediate?alert_source=check_api_latency_p95",
            headers=admin_headers,
        )

        assert response.status_code == 400
        assert "disabled" in response.json()["detail"].lower()


def test_trigger_remediation_no_action(db: Session, admin_headers):
    """Test POST /api/v1/ops/remediate with unmapped source."""
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.auto_remediation_enabled = True

        response = client.post(
            "/api/v1/ops/remediate?alert_source=unknown_detector",
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert "no remediation" in response.json()["detail"].lower()


def test_get_slo_compliance_default_dates(db: Session):
    """Test GET /api/v1/ops/slo with default dates."""
    response = client.get("/api/v1/ops/slo")

    assert response.status_code == 200
    data = response.json()

    assert "d_from" in data
    assert "d_to" in data
    assert "ingest" in data
    assert "scheduler" in data
    assert "api_latency" in data
    assert "overall_pass" in data


def test_get_slo_compliance_custom_dates(db: Session):
    """Test GET /api/v1/ops/slo with custom date range."""
    d_from = date.today() - timedelta(days=14)
    d_to = date.today()

    response = client.get(f"/api/v1/ops/slo?date_from={d_from}&date_to={d_to}")

    assert response.status_code == 200
    data = response.json()

    assert data["d_from"] == str(d_from)
    assert data["d_to"] == str(d_to)


def test_get_slo_compliance_invalid_date_range(db: Session):
    """Test GET /api/v1/ops/slo with invalid date range."""
    d_from = date.today()
    d_to = date.today() - timedelta(days=7)  # d_to before d_from

    response = client.get(f"/api/v1/ops/slo?date_from={d_from}&date_to={d_to}")

    assert response.status_code == 400
    assert "date_from" in response.json()["detail"].lower()


def test_get_slo_summary_default(db: Session):
    """Test GET /api/v1/ops/slo/summary with default 7 days."""
    response = client.get("/api/v1/ops/slo/summary")

    assert response.status_code == 200
    data = response.json()

    assert "d_from" in data
    assert "d_to" in data


def test_get_slo_summary_custom_days(db: Session):
    """Test GET /api/v1/ops/slo/summary with custom days."""
    response = client.get("/api/v1/ops/slo/summary?days=14")

    assert response.status_code == 200
    data = response.json()

    d_from = date.fromisoformat(data["d_from"])
    d_to = date.fromisoformat(data["d_to"])

    delta = (d_to - d_from).days
    assert delta == 13  # 14 days inclusive
