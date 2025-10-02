"""Tests for dashboard API endpoints."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import SKU, Base, DailySales
from app.web.main import app


@pytest.fixture
def test_db():
    """Create in-memory test database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)

    # Insert test data
    sku1 = SKU(marketplace="WB", nm_id="12345", article="TEST-001")
    session.add(sku1)
    session.flush()

    today = date.today()
    for i in range(7):
        d = today - timedelta(days=i)
        session.add(
            DailySales(
                d=d,
                sku_id=sku1.id,
                warehouse_id=None,
                qty=10 + i,
                revenue_gross=1000 + i * 100,
                refunds_qty=1,
                refunds_amount=100,
                promo_cost=50,
                delivery_cost=30,
                commission_amount=120,
                src_hash=f"test_hash_{i}",
            )
        )

    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(test_db, monkeypatch):
    """Create test client with mocked dependencies."""

    # Mock get_db dependency
    def override_get_db():
        yield test_db

    # Mock current_user dependency (bypass auth for tests)
    def override_current_user():
        return {"id": "test_user", "is_admin": True}

    from app.web.deps import current_user, get_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_user] = override_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_get_dashboard_summary(client):
    """Test dashboard summary endpoint."""
    today = date.today()
    week_ago = today - timedelta(days=6)

    response = client.get(f"/api/v1/dashboard/summary?date_from={week_ago}&date_to={today}")

    assert response.status_code == 200
    data = response.json()

    assert "revenue_net" in data
    assert "profit" in data
    assert "margin" in data
    assert "units" in data
    assert "refunds_qty" in data

    # Check calculations
    assert data["units"] > 0  # Should have sales
    assert data["revenue_net"] > 0


def test_get_top_sku(client):
    """Test top SKU endpoint."""
    today = date.today()
    week_ago = today - timedelta(days=6)

    response = client.get(
        f"/api/v1/dashboard/top-sku?date_from={week_ago}&date_to={today}&metric=revenue&limit=10"
    )

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    if len(data) > 0:
        assert "sku_id" in data[0]
        assert "metric_value" in data[0]
        assert "marketplace" in data[0]


def test_dashboard_summary_invalid_dates(client):
    """Test dashboard summary with invalid date range."""
    response = client.get("/api/v1/dashboard/summary?date_from=invalid&date_to=2024-01-01")

    assert response.status_code == 422  # Validation error
