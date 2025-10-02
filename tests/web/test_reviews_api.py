"""Tests for reviews API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Review
from app.web.main import app


@pytest.fixture
def test_db():
    """Create in-memory test database with review data."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)

    # Insert test reviews
    session.add(
        Review(
            review_id="REV001",
            marketplace="WB",
            sku_key="12345",
            rating=5,
            text="Great product!",
            created_at_utc=datetime.now(UTC),
            reply_status=None,
        )
    )
    session.add(
        Review(
            review_id="REV002",
            marketplace="OZON",
            sku_key="67890",
            rating=3,
            text="Average quality",
            created_at_utc=datetime.now(UTC),
            reply_status=None,
        )
    )
    session.add(
        Review(
            review_id="REV003",
            marketplace="WB",
            sku_key="11111",
            rating=4,
            text="Good",
            created_at_utc=datetime.now(UTC),
            reply_status="sent",
            reply_text="Thank you!",
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


def test_get_reviews_all(client):
    """Test getting all reviews."""
    response = client.get("/api/v1/reviews")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 3  # All 3 reviews


def test_get_reviews_pending_only(client):
    """Test getting pending reviews only."""
    response = client.get("/api/v1/reviews?status=pending")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 2  # Only pending reviews
    assert all(r["reply_status"] is None for r in data)


def test_get_reviews_sent_only(client):
    """Test getting sent reviews only."""
    response = client.get("/api/v1/reviews?status=sent")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1  # Only sent review
    assert data[0]["review_id"] == "REV003"
    assert data[0]["reply_status"] == "sent"


def test_post_review_reply(client):
    """Test posting a reply to a review."""
    response = client.post(
        "/api/v1/reviews/REV001/reply", json={"text": "Thank you for your feedback!"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["review_id"] == "REV001"

    # Verify review was updated
    review_response = client.get("/api/v1/reviews?status=sent")
    reviews = review_response.json()
    replied_review = next((r for r in reviews if r["review_id"] == "REV001"), None)

    assert replied_review is not None
    assert replied_review["reply_status"] == "sent"
    assert replied_review["reply_text"] == "Thank you for your feedback!"


def test_post_reply_already_sent(client):
    """Test replying to already-sent review fails."""
    response = client.post("/api/v1/reviews/REV003/reply", json={"text": "Another reply"})

    assert response.status_code == 400
    assert "already replied" in response.json()["detail"].lower()


def test_post_reply_not_found(client):
    """Test replying to non-existent review."""
    response = client.post("/api/v1/reviews/INVALID/reply", json={"text": "Test"})

    assert response.status_code == 404
