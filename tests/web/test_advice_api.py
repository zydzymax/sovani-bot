"""Tests for advice/recommendations API endpoints."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import SKU, AdviceSupply, Base, DailyStock, MetricsDaily, Warehouse
from app.web.main import app


@pytest.fixture
def test_db():
    """Create in-memory test database with advice data."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)

    # Create test SKU and warehouse
    sku1 = SKU(marketplace="WB", nm_id="12345", article="TEST-001")
    wh1 = Warehouse(marketplace="WB", code="MSK", name="Moscow")
    session.add_all([sku1, wh1])
    session.flush()

    today = date.today()

    # Add metrics
    session.add(
        MetricsDaily(
            d=today,
            sku_id=sku1.id,
            revenue_net=1000.0,
            cogs=500.0,
            profit=500.0,
            margin=50.0,
            sv7=2.5,
            sv14=3.1,
            sv28=2.8,
            stock_cover_days=10,
        )
    )

    # Add stock
    session.add(
        DailyStock(
            d=today,
            sku_id=sku1.id,
            warehouse_id=wh1.id,
            on_hand=20,
            in_transit=10,
            src_hash="test_hash",
        )
    )

    # Add advice for 14 and 28 day windows
    session.add(
        AdviceSupply(
            d=today,
            sku_id=sku1.id,
            warehouse_id=wh1.id,
            window_days=14,
            recommended_qty=25,
            rationale_hash="hash_14",
        )
    )
    session.add(
        AdviceSupply(
            d=today,
            sku_id=sku1.id,
            warehouse_id=wh1.id,
            window_days=28,
            recommended_qty=45,
            rationale_hash="hash_28",
        )
    )

    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(test_db):
    """Create test client with mocked dependencies."""

    def override_get_db():
        yield test_db

    def override_current_user():
        return {"id": "test_user", "is_admin": True}

    from app.web.deps import current_user, get_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_user] = override_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_get_advice_all(client):
    """Test getting all advice for today."""
    today = date.today()
    response = client.get(f"/api/v1/advice?date={today}")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 2  # Both 14 and 28 day windows


def test_get_advice_filtered_by_window(client):
    """Test filtering advice by planning window."""
    today = date.today()
    response = client.get(f"/api/v1/advice?date={today}&window=14")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["window_days"] == 14
    assert data[0]["recommended_qty"] == 25


def test_get_advice_with_explanation(client):
    """Test that advice includes explanation."""
    today = date.today()
    response = client.get(f"/api/v1/advice?date={today}")

    assert response.status_code == 200
    data = response.json()

    assert len(data) > 0
    advice_row = data[0]

    # Check required fields
    assert "sku_id" in advice_row
    assert "recommended_qty" in advice_row
    assert "explain" in advice_row

    # Explanation should be generated
    if advice_row["explain"]:
        assert "SV" in advice_row["explain"]
        assert "рекомендовано" in advice_row["explain"]


def test_get_advice_filtered_by_sku(client, test_db):
    """Test filtering advice by SKU ID."""
    today = date.today()

    # Get SKU ID from test data
    from app.db.models import SKU

    sku = test_db.query(SKU).first()

    response = client.get(f"/api/v1/advice?date={today}&sku_id={sku.id}")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert all(r["sku_id"] == sku.id for r in data)


def test_get_advice_empty_result(client):
    """Test advice endpoint with no data for future date."""
    future_date = date(2030, 1, 1)
    response = client.get(f"/api/v1/advice?date={future_date}")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 0
