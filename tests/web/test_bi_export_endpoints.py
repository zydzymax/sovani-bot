"""Tests for BI export endpoints."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.web.main import app

client = TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    with patch("app.web.routers.bi_export.get_db") as mock_get_db:
        mock_session = MagicMock()
        mock_get_db.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_auth():
    """Mock authentication."""
    with patch("app.web.routers.bi_export.current_user") as mock_user:
        mock_user.return_value = {"id": "test_user", "role": "admin"}
        yield mock_user


def test_pnl_csv_export(mock_db_session, mock_auth):
    """Test P&L CSV export with date range filter."""
    # Mock database response
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {
            "d": date(2025, 9, 1),
            "sku_id": 1,
            "article": "TEST-001",
            "warehouse_id": 1,
            "warehouse": "WB:Москва",
            "marketplace": "WB",
            "units": 10,
            "revenue_net_gross": 10000.0,
            "revenue_net": 8000.0,
            "unit_cost": 500.0,
            "profit_approx": 3000.0,
            "sv14": 5.5,
            "sv28": 6.2,
        }
    ]
    mock_db_session.execute.return_value = mock_result

    response = client.get(
        "/api/v1/export/bi/pnl.csv",
        params={
            "date_from": "2025-09-01",
            "date_to": "2025-09-30",
            "marketplace": "WB",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert "TEST-001" in response.text


def test_pnl_xlsx_export(mock_db_session, mock_auth):
    """Test P&L XLSX export."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result

    response = client.get(
        "/api/v1/export/bi/pnl.xlsx",
        params={
            "date_from": "2025-09-01",
            "date_to": "2025-09-30",
        },
    )

    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert "pnl.xlsx" in response.headers["content-disposition"]


def test_inventory_csv_export(mock_db_session, mock_auth):
    """Test inventory snapshot CSV export."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {
            "sku_id": 1,
            "warehouse_id": 1,
            "warehouse": "WB:Москва",
            "on_hand": 50,
            "in_transit": 20,
            "d": date.today(),
        }
    ]
    mock_db_session.execute.return_value = mock_result

    response = client.get("/api/v1/export/bi/inventory.csv")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "50" in response.text  # on_hand value


def test_supply_advice_csv_export(mock_db_session, mock_auth):
    """Test supply advice CSV export."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {
            "d": date.today(),
            "sku_id": 1,
            "article": "TEST-001",
            "warehouse_id": 1,
            "warehouse": "WB:Москва",
            "window_days": 14,
            "recommended_qty": 100,
            "rationale_hash": "abc123",
        }
    ]
    mock_db_session.execute.return_value = mock_result

    response = client.get(
        "/api/v1/export/bi/supply_advice.csv",
        params={"window_days": 14},
    )

    assert response.status_code == 200
    assert "TEST-001" in response.text


def test_pricing_advice_csv_export(mock_db_session, mock_auth):
    """Test pricing advice CSV export."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {
            "d": date.today(),
            "sku_id": 1,
            "article": "TEST-001",
            "suggested_price": 950.0,
            "suggested_discount_pct": 0.05,
            "expected_profit": 350.0,
            "quality": "medium",
            "reason_code": "elasticity_based",
            "rationale_hash": "xyz789",
        }
    ]
    mock_db_session.execute.return_value = mock_result

    response = client.get(
        "/api/v1/export/bi/pricing_advice.csv",
        params={"quality": "medium"},
    )

    assert response.status_code == 200
    assert "950.0" in response.text
    assert "elasticity_based" in response.text


def test_reviews_summary_csv_export(mock_db_session, mock_auth):
    """Test reviews summary CSV export."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {
            "marketplace": "WB",
            "sku_id": 1,
            "article": "TEST-001",
            "d": date.today(),
            "reviews_total": 15,
            "rating_avg": 4.5,
            "replies_sent": 12,
        }
    ]
    mock_db_session.execute.return_value = mock_result

    response = client.get(
        "/api/v1/export/bi/reviews_summary.csv",
        params={
            "date_from": str(date.today() - timedelta(days=7)),
            "date_to": str(date.today()),
            "marketplace": "WB",
        },
    )

    assert response.status_code == 200
    assert "4.5" in response.text  # rating_avg


def test_export_with_filters(mock_db_session, mock_auth):
    """Test export with multiple filters."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result

    response = client.get(
        "/api/v1/export/bi/pnl.csv",
        params={
            "date_from": "2025-09-01",
            "date_to": "2025-09-30",
            "sku_id": 123,
            "warehouse_id": 1,
            "marketplace": "OZON",
            "limit": 100,
            "offset": 50,
        },
    )

    assert response.status_code == 200
    # Verify SQL parameters were passed correctly
    call_args = mock_db_session.execute.call_args
    params = call_args[0][1]
    assert params["sku_id"] == 123
    assert params["warehouse_id"] == 1
    assert params["marketplace"] == "OZON"
    assert params["lim"] == 100
    assert params["off"] == 50


def test_export_limit_enforcement(mock_db_session, mock_auth):
    """Test that export limits are enforced."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result

    # Request exceeding max limit
    response = client.get(
        "/api/v1/export/bi/inventory.csv",
        params={"limit": 200000},  # Over max of 100000
    )

    assert response.status_code == 200
    # Verify limit was capped at max
    call_args = mock_db_session.execute.call_args
    params = call_args[0][1]
    assert params["lim"] == 100000


def test_export_default_limit(mock_db_session, mock_auth):
    """Test default limit when not specified."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result

    response = client.get(
        "/api/v1/export/bi/pricing_advice.csv"
        # No limit parameter
    )

    assert response.status_code == 200
    call_args = mock_db_session.execute.call_args
    params = call_args[0][1]
    assert params["lim"] == 5000  # Default limit


def test_export_requires_authentication(mock_db_session):
    """Test that exports require authentication."""
    with patch("app.web.routers.bi_export.current_user") as mock_user:
        # Mock authentication failure
        from fastapi import HTTPException

        mock_user.side_effect = HTTPException(status_code=401, detail="Unauthorized")

        response = client.get(
            "/api/v1/export/bi/pnl.csv",
            params={"date_from": "2025-09-01", "date_to": "2025-09-30"},
        )

        assert response.status_code == 401
