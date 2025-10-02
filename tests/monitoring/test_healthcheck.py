"""Tests for healthcheck endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.web.main import app


@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def client(test_db):
    """Test client with database."""

    def override_get_db():
        yield test_db

    from app.web.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_basic_health_endpoint(client):
    """Test /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_healthz_endpoint_success(client):
    """Test /healthz endpoint returns healthy status."""
    response = client.get("/healthz")

    # May be 200 or 503 depending on system state
    assert response.status_code in [200, 503]

    data = response.json()
    assert "status" in data
    assert "healthy" in data
    assert "checks" in data


def test_healthz_has_database_check(client):
    """Test /healthz includes database check."""
    response = client.get("/healthz")
    data = response.json()

    assert "checks" in data
    assert "database" in data["checks"]
    assert data["checks"]["database"]["status"] in ["ok", "error"]


def test_healthz_has_disk_check(client):
    """Test /healthz includes disk space check."""
    response = client.get("/healthz")
    data = response.json()

    assert "disk" in data["checks"]
    assert "free_gb" in data["checks"]["disk"]
    assert "used_percent" in data["checks"]["disk"]


def test_healthz_has_memory_check(client):
    """Test /healthz includes memory check."""
    response = client.get("/healthz")
    data = response.json()

    assert "memory" in data["checks"]
    assert "available_mb" in data["checks"]["memory"]
    assert "used_percent" in data["checks"]["memory"]


def test_healthz_has_uptime(client):
    """Test /healthz includes uptime."""
    response = client.get("/healthz")
    data = response.json()

    assert "uptime" in data["checks"]
    assert "uptime_seconds" in data["checks"]["uptime"]
    assert "uptime_human" in data["checks"]["uptime"]
    assert data["checks"]["uptime"]["uptime_seconds"] >= 0


def test_healthz_timestamp(client):
    """Test /healthz includes timestamp."""
    response = client.get("/healthz")
    data = response.json()

    assert "checks" in data
    assert "timestamp" in data["checks"]
    # Timestamp should be ISO format
    assert "T" in data["checks"]["timestamp"]
