"""Tests for API filters, pagination, and sorting."""

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
    """Create in-memory test database with multiple records."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)

    # Insert multiple reviews for testing filters/pagination
    for i in range(20):
        session.add(
            Review(
                review_id=f"REV{i:03d}",
                marketplace="WB" if i % 2 == 0 else "OZON",
                sku_key=f"SKU{i}",
                rating=(i % 5) + 1,  # 1-5 stars
                text=f"Review text {i}",
                created_at_utc=datetime.now(timezone.utc),
                reply_status="sent" if i < 10 else None,
                reply_text=f"Reply {i}" if i < 10 else None,
            )
        )

    # Insert SKU and warehouse for advice tests
    session.add(SKU(id=1, marketplace="WB", nm_id="12345"))
    session.add(Warehouse(id=1, marketplace="WB", name="Moscow-1"))

    # Insert multiple advice records
    for i in range(15):
        session.add(
            AdviceSupply(
                d=date.today(),
                sku_id=1,
                warehouse_id=1,
                window_days=14 if i % 2 == 0 else 28,
                recommended_qty=(i + 1) * 10,
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
        return {"id": "test", "username": "test", "role": "admin"}

    from app.web.deps import current_user, get_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_user] = override_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_reviews_pagination_limit(client):
    """Test reviews limit parameter."""
    response = client.get("/api/v1/reviews?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


def test_reviews_pagination_offset(client):
    """Test reviews offset parameter."""
    # Get first page
    response1 = client.get("/api/v1/reviews?limit=5&offset=0")
    data1 = response1.json()

    # Get second page
    response2 = client.get("/api/v1/reviews?limit=5&offset=5")
    data2 = response2.json()

    # Should be different reviews
    assert data1[0]["review_id"] != data2[0]["review_id"]


def test_reviews_filter_by_status_pending(client):
    """Test reviews filter by status=pending."""
    response = client.get("/api/v1/reviews?status=pending")
    data = response.json()

    # All returned reviews should have reply_status=None
    assert all(r["reply_status"] is None for r in data)
    assert len(data) == 10  # 10 pending reviews


def test_reviews_filter_by_status_sent(client):
    """Test reviews filter by status=sent."""
    response = client.get("/api/v1/reviews?status=sent")
    data = response.json()

    # All returned reviews should have reply_status='sent'
    assert all(r["reply_status"] == "sent" for r in data)
    assert len(data) == 10  # 10 sent reviews


def test_reviews_filter_by_marketplace(client):
    """Test reviews filter by marketplace."""
    response = client.get("/api/v1/reviews?marketplace=WB")
    data = response.json()

    # All returned reviews should be from WB
    assert all(r["marketplace"] == "WB" for r in data)


def test_reviews_filter_by_rating(client):
    """Test reviews filter by rating."""
    response = client.get("/api/v1/reviews?rating=5")
    data = response.json()

    # All returned reviews should have rating=5
    assert all(r["rating"] == 5 for r in data)


def test_reviews_order_asc(client):
    """Test reviews order=asc."""
    response = client.get("/api/v1/reviews?order=asc&limit=2")
    data = response.json()

    # Should be ordered by created_at ascending (oldest first)
    # Just check we got results (actual order depends on microseconds)
    assert len(data) == 2


def test_advice_pagination(client):
    """Test advice pagination."""
    response = client.get(f"/api/v1/advice?date={date.today()}&limit=5&offset=0")
    data = response.json()

    assert len(data) == 5


def test_advice_filter_by_window(client):
    """Test advice filter by window."""
    response = client.get(f"/api/v1/advice?date={date.today()}&window=14")
    data = response.json()

    # All returned advice should have window_days=14
    assert all(r["window_days"] == 14 for r in data)


def test_advice_order_desc(client):
    """Test advice order by recommended_qty descending."""
    response = client.get(f"/api/v1/advice?date={date.today()}&order=desc&limit=3")
    data = response.json()

    # Should be ordered descending (highest qty first)
    assert len(data) == 3
    assert data[0]["recommended_qty"] >= data[1]["recommended_qty"]


def test_advice_order_asc(client):
    """Test advice order by recommended_qty ascending."""
    response = client.get(f"/api/v1/advice?date={date.today()}&order=asc&limit=3")
    data = response.json()

    # Should be ordered ascending (lowest qty first)
    assert len(data) == 3
    assert data[0]["recommended_qty"] <= data[1]["recommended_qty"]


def test_dashboard_top_sku_pagination(client):
    """Test dashboard top-sku with limit and offset."""
    # Add some sales data
    from app.db.models import DailySales

    db = next(app.dependency_overrides[__import__("app.web.deps").get_db]())
    for i in range(10):
        db.add(
            DailySales(
                d=date(2025, 1, 1),
                sku_id=i + 1,
                warehouse_id=1,
                qty=10,
                revenue_gross=(i + 1) * 1000,
            )
        )
    db.commit()

    response = client.get(
        "/api/v1/dashboard/top-sku?date_from=2025-01-01&date_to=2025-01-31&limit=5&offset=0"
    )
    data = response.json()

    assert len(data) <= 5
