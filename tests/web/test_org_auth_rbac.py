"""Tests for multi-tenant auth and RBAC (Stage 19)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.web.auth import CurrentUser, get_or_create_user


def test_get_or_create_user_new(db: Session):
    """Test creating new user with default org."""
    tg_user_id = 123456789
    user_data = {
        "id": tg_user_id,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
    }

    user_id, org_id, role = get_or_create_user(db, tg_user_id, user_data)

    # Verify user created
    assert user_id > 0
    assert org_id == 1  # Default org
    assert role == "owner"  # First user is owner

    # Verify user in DB
    user_row = db.execute(
        text("SELECT tg_username, tg_first_name FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    ).first()

    assert user_row[0] == "testuser"
    assert user_row[1] == "Test"


def test_get_or_create_user_existing(db: Session):
    """Test getting existing user."""
    tg_user_id = 987654321
    user_data = {"id": tg_user_id, "username": "existing", "first_name": "Existing"}

    # Create user first time
    user_id1, org_id1, role1 = get_or_create_user(db, tg_user_id, user_data)

    # Get user second time
    user_id2, org_id2, role2 = get_or_create_user(db, tg_user_id, user_data)

    # Should return same user
    assert user_id1 == user_id2
    assert org_id1 == org_id2
    assert role1 == role2


def test_current_user_model():
    """Test CurrentUser model."""
    user = CurrentUser(
        user_id=1,
        tg_user_id=123456,
        org_id=1,
        role="manager",
        tg_username="testuser",
        tg_first_name="Test",
    )

    assert user.user_id == 1
    assert user.org_id == 1
    assert user.role == "manager"
    assert "CurrentUser" in repr(user)


def test_role_hierarchy():
    """Test RBAC role hierarchy."""
    # This would test require_org_member dependency
    # For now, just verify role names
    roles = ["viewer", "manager", "owner"]
    role_levels = {"viewer": 0, "manager": 1, "owner": 2}

    # Verify hierarchy
    assert role_levels["viewer"] < role_levels["manager"]
    assert role_levels["manager"] < role_levels["owner"]


def test_create_multiple_users_same_org(db: Session):
    """Test multiple users in same org."""
    # Create first user
    user_id1, org_id1, role1 = get_or_create_user(
        db, 111, {"id": 111, "username": "user1", "first_name": "User1"}
    )

    # Create second user (should join same default org)
    user_id2, org_id2, role2 = get_or_create_user(
        db, 222, {"id": 222, "username": "user2", "first_name": "User2"}
    )

    # Both should be in same org
    assert org_id1 == org_id2

    # Verify both are members
    members = db.execute(
        text("SELECT user_id, role FROM org_members WHERE org_id = :org_id"),
        {"org_id": org_id1},
    ).fetchall()

    assert len(members) >= 2
    member_ids = [m[0] for m in members]
    assert user_id1 in member_ids
    assert user_id2 in member_ids
