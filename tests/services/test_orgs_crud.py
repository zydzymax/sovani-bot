"""Tests for organizations CRUD service (Stage 19)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.orgs import (
    change_member_role,
    create_organization,
    get_credentials,
    get_user_organizations,
    invite_member,
    list_members,
    remove_member,
    update_credentials,
)


def test_create_organization(db: Session):
    """Test creating new organization."""
    # Create test user
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (1, 111)"))
    db.commit()

    # Create org
    org = create_organization(db, "Test Org", creator_user_id=1)

    assert org["org_id"] > 0
    assert org["name"] == "Test Org"

    # Verify creator is owner
    membership = db.execute(
        text("SELECT role FROM org_members WHERE org_id = :org_id AND user_id = 1"),
        {"org_id": org["org_id"]},
    ).first()

    assert membership[0] == "owner"


def test_create_organization_duplicate_name(db: Session):
    """Test creating org with duplicate name fails."""
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (2, 222)"))
    db.commit()

    create_organization(db, "Unique Org", creator_user_id=2)

    # Try to create duplicate
    with pytest.raises(ValueError, match="already exists"):
        create_organization(db, "Unique Org", creator_user_id=2)


def test_invite_member(db: Session):
    """Test inviting user to organization."""
    # Setup
    db.execute(text("INSERT INTO organizations (id, name) VALUES (10, 'Team Org')"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (3, 333)"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (4, 444)"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (10, 3, 'owner')"))
    db.commit()

    # Invite user 4 as manager
    result = invite_member(db, org_id=10, tg_user_id=444, role="manager", inviter_user_id=3)

    assert result["user_id"] == 4
    assert result["role"] == "manager"

    # Verify in DB
    membership = db.execute(
        text("SELECT role FROM org_members WHERE org_id = 10 AND user_id = 4")
    ).first()

    assert membership[0] == "manager"


def test_invite_member_already_exists(db: Session):
    """Test inviting existing member fails."""
    db.execute(text("INSERT INTO organizations (id, name) VALUES (11, 'Existing Org')"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (5, 555)"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (11, 5, 'viewer')"))
    db.commit()

    with pytest.raises(ValueError, match="already member"):
        invite_member(db, org_id=11, tg_user_id=555, role="manager", inviter_user_id=5)


def test_change_member_role(db: Session):
    """Test changing member's role."""
    db.execute(text("INSERT INTO organizations (id, name) VALUES (12, 'Change Org')"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (6, 666)"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (12, 6, 'viewer')"))
    db.commit()

    # Change to manager
    result = change_member_role(db, org_id=12, user_id=6, new_role="manager", changer_user_id=1)

    assert result["role"] == "manager"

    # Verify in DB
    membership = db.execute(
        text("SELECT role FROM org_members WHERE org_id = 12 AND user_id = 6")
    ).first()

    assert membership[0] == "manager"


def test_remove_member(db: Session):
    """Test removing member from org."""
    db.execute(text("INSERT INTO organizations (id, name) VALUES (13, 'Remove Org')"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (7, 777)"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (8, 888)"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (13, 7, 'owner')"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (13, 8, 'viewer')"))
    db.commit()

    # Remove viewer
    remove_member(db, org_id=13, user_id=8, remover_user_id=7)

    # Verify removed
    membership = db.execute(
        text("SELECT user_id FROM org_members WHERE org_id = 13 AND user_id = 8")
    ).first()

    assert membership is None


def test_remove_last_owner_fails(db: Session):
    """Test cannot remove last owner."""
    db.execute(text("INSERT INTO organizations (id, name) VALUES (14, 'Protect Org')"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (9, 999)"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (14, 9, 'owner')"))
    db.commit()

    with pytest.raises(ValueError, match="Cannot remove last owner"):
        remove_member(db, org_id=14, user_id=9, remover_user_id=9)


def test_list_members(db: Session):
    """Test listing org members."""
    db.execute(text("INSERT INTO organizations (id, name) VALUES (15, 'List Org')"))
    db.execute(text("INSERT INTO users (id, tg_user_id, tg_username) VALUES (10, 1010, 'user10')"))
    db.execute(text("INSERT INTO users (id, tg_user_id, tg_username) VALUES (11, 1111, 'user11')"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (15, 10, 'owner')"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (15, 11, 'manager')"))
    db.commit()

    members = list_members(db, org_id=15)

    assert len(members) == 2
    usernames = [m["tg_username"] for m in members]
    assert "user10" in usernames
    assert "user11" in usernames


def test_get_user_organizations(db: Session):
    """Test getting user's orgs."""
    db.execute(text("INSERT INTO organizations (id, name) VALUES (16, 'Org A')"))
    db.execute(text("INSERT INTO organizations (id, name) VALUES (17, 'Org B')"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (12, 1212)"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (16, 12, 'owner')"))
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (17, 12, 'viewer')"))
    db.commit()

    orgs = get_user_organizations(db, user_id=12)

    assert len(orgs) == 2
    org_names = [o["name"] for o in orgs]
    assert "Org A" in org_names
    assert "Org B" in org_names


def test_update_credentials(db: Session):
    """Test updating org credentials."""
    db.execute(text("INSERT INTO organizations (id, name) VALUES (18, 'Cred Org')"))
    db.commit()

    # Update credentials
    update_credentials(
        db,
        org_id=18,
        credentials={"wb_feedbacks_token": "test_token_123", "ozon_client_id": "client_456"},
        updater_user_id=1,
    )

    # Verify
    creds = get_credentials(db, org_id=18)

    assert creds["wb_feedbacks_token"] == "test_token_123"
    assert creds["ozon_client_id"] == "client_456"


def test_get_credentials_not_exist(db: Session):
    """Test getting credentials for org without credentials."""
    db.execute(text("INSERT INTO organizations (id, name) VALUES (19, 'No Creds Org')"))
    db.commit()

    creds = get_credentials(db, org_id=19)

    # Should return dict with None values
    assert creds["wb_feedbacks_token"] is None
    assert creds["ozon_client_id"] is None
