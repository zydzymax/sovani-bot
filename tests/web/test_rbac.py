"""Tests for RBAC (Role-Based Access Control)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.web.main import app


@pytest.fixture
def test_db():
    """Create in-memory test database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def client_admin(test_db):
    """Test client with admin user."""

    def override_get_db():
        yield test_db

    def override_current_user():
        return {"id": "123", "username": "admin_user", "role": "admin"}

    from app.web.deps import current_user, get_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_user] = override_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def client_viewer(test_db):
    """Test client with viewer (read-only) user."""

    def override_get_db():
        yield test_db

    def override_current_user():
        return {"id": "456", "username": "viewer_user", "role": "viewer"}

    from app.web.deps import current_user, get_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_user] = override_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def client_unauthorized():
    """Test client without authentication."""

    def override_current_user():
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="User not authorized")

    from app.web.deps import current_user

    app.dependency_overrides[current_user] = override_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_admin_can_read(client_admin):
    """Admin users can read data."""
    response = client_admin.get("/api/v1/reviews?limit=10")
    assert response.status_code == 200


def test_viewer_can_read(client_viewer):
    """Viewer users can read data."""
    response = client_viewer.get("/api/v1/reviews?limit=10")
    assert response.status_code == 200


def test_unauthorized_cannot_read(client_unauthorized):
    """Unauthorized users cannot read data."""
    response = client_unauthorized.get("/api/v1/reviews?limit=10")
    assert response.status_code == 403


def test_admin_can_post_review_reply(client_admin):
    """Admin users can POST review replies."""
    # Note: This will fail with 404 since review doesn't exist, but auth should pass
    response = client_admin.post(
        "/api/v1/reviews/TEST123/reply", json={"text": "Thank you!"}
    )
    # Should NOT be 403 Forbidden - admin has permission
    # Will be 404 Not Found since review doesn't exist
    assert response.status_code in [200, 404], f"Got {response.status_code}: {response.json()}"


def test_viewer_cannot_post_review_reply(client_viewer):
    """Viewer users cannot POST review replies (403 Forbidden)."""
    response = client_viewer.post(
        "/api/v1/reviews/TEST123/reply", json={"text": "Thank you!"}
    )
    # Viewer should get 403 Forbidden due to require_admin dependency
    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


def test_unauthorized_cannot_post(client_unauthorized):
    """Unauthorized users cannot POST."""
    response = client_unauthorized.post(
        "/api/v1/reviews/TEST123/reply", json={"text": "Thank you!"}
    )
    assert response.status_code == 403
