"""Tests for pricing API endpoints (Stage 14)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import SKU, Base, PricingAdvice
from app.web.main import app


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Create test SKUs
        sku1 = SKU(id=1, marketplace="WB", nm_id="12345", article="TEST-001")
        sku2 = SKU(id=2, marketplace="OZON", ozon_id="67890", article="TEST-002")
        session.add_all([sku1, sku2])

        # Add pricing advice
        today = date.today()
        advice1 = PricingAdvice(
            d=today,
            sku_id=1,
            suggested_price=950.0,
            suggested_discount_pct=0.05,
            expected_profit=350.0,
            quality="medium",
            rationale_hash="abc123",
            reason_code="discount",
        )
        advice2 = PricingAdvice(
            d=today,
            sku_id=2,
            suggested_price=None,
            suggested_discount_pct=None,
            expected_profit=0.0,
            quality="low",
            rationale_hash="xyz789",
            reason_code="keep",
        )
        session.add_all([advice1, advice2])

        session.commit()
        yield session


@pytest.fixture
def client(test_db):
    """Create test client with mocked database."""
    with patch("app.web.routers.pricing.get_db") as mock_get_db:
        mock_get_db.return_value = test_db
        yield TestClient(app)


def test_get_pricing_advice_no_filters(client):
    """Test GET /api/v1/pricing/advice without filters."""
    response = client.get("/api/v1/pricing/advice")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


def test_get_pricing_advice_filter_by_marketplace(client):
    """Test GET /api/v1/pricing/advice with marketplace filter."""
    response = client.get("/api/v1/pricing/advice?marketplace=WB")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["marketplace"] == "WB"
    assert data[0]["article"] == "TEST-001"


def test_get_pricing_advice_filter_by_sku_id(client):
    """Test GET /api/v1/pricing/advice with sku_id filter."""
    response = client.get("/api/v1/pricing/advice?sku_id=2")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["sku_id"] == 2


def test_get_pricing_advice_filter_by_quality(client):
    """Test GET /api/v1/pricing/advice with quality filter."""
    response = client.get("/api/v1/pricing/advice?quality=medium")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["quality"] == "medium"


def test_get_pricing_advice_pagination(client):
    """Test GET /api/v1/pricing/advice with pagination."""
    response = client.get("/api/v1/pricing/advice?limit=1&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1


def test_post_compute_pricing_requires_admin(client):
    """Test POST /api/v1/pricing/compute requires admin authentication."""
    with patch("app.web.routers.pricing.require_admin") as mock_admin:
        # Mock admin check to fail
        mock_admin.side_effect = Exception("Unauthorized")

        response = client.post("/api/v1/pricing/compute")

        # Should fail without admin
        assert response.status_code == 500  # Or whatever error code your app uses


def test_post_compute_pricing_success(client):
    """Test POST /api/v1/pricing/compute with admin auth."""
    with (
        patch("app.web.routers.pricing.require_admin") as mock_admin,
        patch("app.web.routers.pricing.compute_pricing_for_skus") as mock_compute,
    ):
        # Mock admin check to succeed
        mock_admin.return_value = {"user_id": 1, "is_admin": True}

        # Mock computation
        mock_compute.return_value = [
            {"sku_id": 1, "suggested_price": 950.0},
            {"sku_id": 2, "suggested_price": None},
        ]

        response = client.post("/api/v1/pricing/compute")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["recommendations_generated"] == 2


def test_post_compute_pricing_with_filters(client):
    """Test POST /api/v1/pricing/compute with marketplace and window filters."""
    with (
        patch("app.web.routers.pricing.require_admin") as mock_admin,
        patch("app.web.routers.pricing.compute_pricing_for_skus") as mock_compute,
    ):
        # Mock admin check
        mock_admin.return_value = {"user_id": 1, "is_admin": True}
        mock_compute.return_value = [{"sku_id": 1}]

        response = client.post("/api/v1/pricing/compute?marketplace=WB&window=14")

        assert response.status_code == 200
        data = response.json()
        assert data["marketplace"] == "WB"
        assert data["window"] == 14

        # Verify compute was called with correct parameters
        mock_compute.assert_called_once()
        call_kwargs = mock_compute.call_args[1]
        assert call_kwargs["marketplace"] == "WB"
        assert call_kwargs["window"] == 14
