"""Tests for CSV/XLSX export endpoints."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import AdviceSupply, Base, DailySales, Review, SKU, Warehouse
from app.web.main import app


@pytest.fixture
def test_db():
    """Create in-memory test database with sample data."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)

    # Insert sample sales data
    session.add(
        DailySales(
            d=date(2025, 1, 1),
            sku_id=1,
            warehouse_id=1,
            qty=10,
            revenue_gross=5000.0,
            refunds_qty=1,
            refunds_amount=500.0,
            promo_cost=100.0,
            delivery_cost=200.0,
            commission_amount=300.0,
        )
    )

    # Insert sample review
    session.add(
        Review(
            review_id="REV001",
            marketplace="WB",
            sku_key="12345",
            rating=5,
            text="Great product!",
            created_at_utc=datetime.now(timezone.utc),
            reply_status=None,
        )
    )

    # Insert sample SKU and warehouse for advice
    session.add(SKU(id=1, marketplace="WB", nm_id="12345", article="ART001"))
    session.add(Warehouse(id=1, marketplace="WB", name="Moscow-1"))
    session.add(
        AdviceSupply(
            d=date.today(),
            sku_id=1,
            warehouse_id=1,
            window_days=14,
            recommended_qty=100,
        )
    )

    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(test_db):
    """Test client with mocked dependencies."""

    def override_get_db():
        yield test_db

    def override_current_user():
        return {"id": "admin", "username": "admin", "role": "admin"}

    from app.web.deps import current_user, get_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_user] = override_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_export_dashboard_csv(client):
    """Test exporting dashboard data as CSV."""
    response = client.get(
        "/api/v1/export/dashboard.csv?date_from=2025-01-01&date_to=2025-01-31"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert "dashboard.csv" in response.headers["content-disposition"]

    # Check CSV content
    content = response.text
    assert "date,revenue_net,units,refunds_qty" in content
    assert "2025-01-01" in content


def test_export_advice_xlsx(client):
    """Test exporting supply advice as XLSX."""
    today = date.today().isoformat()
    response = client.get(f"/api/v1/export/advice.xlsx?date={today}")

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in response.headers["content-disposition"]
    assert "advice.xlsx" in response.headers["content-disposition"]

    # XLSX content is binary, just check it's not empty
    assert len(response.content) > 0


def test_export_reviews_csv(client):
    """Test exporting reviews as CSV."""
    response = client.get("/api/v1/export/reviews.csv?status=pending")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert "reviews.csv" in response.headers["content-disposition"]

    # Check CSV content
    content = response.text
    assert "review_id,marketplace,sku_key,rating,text" in content
    assert "REV001" in content
    assert "Great product!" in content


def test_export_advice_with_window_filter(client):
    """Test exporting advice with window filter."""
    today = date.today().isoformat()
    response = client.get(f"/api/v1/export/advice.xlsx?date={today}&window=14")

    assert response.status_code == 200
    assert len(response.content) > 0


def test_export_reviews_with_marketplace_filter(client):
    """Test exporting reviews with marketplace filter."""
    response = client.get("/api/v1/export/reviews.csv?marketplace=WB")

    assert response.status_code == 200
    content = response.text
    assert "REV001" in content
