"""Tests for org_id scoping and data isolation (Stage 19)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def test_org_data_isolation_sku(db: Session):
    """Test that SKUs are isolated by org_id."""
    # Create two orgs
    db.execute(text("INSERT INTO organizations (id, name) VALUES (10, 'Org A')"))
    db.execute(text("INSERT INTO organizations (id, name) VALUES (20, 'Org B')"))
    db.commit()

    # Create SKUs for each org
    db.execute(
        text(
            """
            INSERT INTO sku (marketplace, nm_id, article, org_id)
            VALUES ('WB', '12345', 'SKU-A', 10)
        """
        )
    )
    db.execute(
        text(
            """
            INSERT INTO sku (marketplace, nm_id, article, org_id)
            VALUES ('WB', '67890', 'SKU-B', 20)
        """
        )
    )
    db.commit()

    # Query for org A
    skus_a = db.execute(text("SELECT article FROM sku WHERE org_id = 10")).fetchall()

    # Query for org B
    skus_b = db.execute(text("SELECT article FROM sku WHERE org_id = 20")).fetchall()

    # Verify isolation
    assert len(skus_a) == 1
    assert skus_a[0][0] == "SKU-A"

    assert len(skus_b) == 1
    assert skus_b[0][0] == "SKU-B"


def test_org_data_isolation_reviews(db: Session):
    """Test that reviews are isolated by org_id."""
    # Create test SKUs
    db.execute(
        text("INSERT INTO sku (id, marketplace, nm_id, org_id) VALUES (100, 'WB', '111', 10)")
    )
    db.execute(
        text("INSERT INTO sku (id, marketplace, nm_id, org_id) VALUES (200, 'WB', '222', 20)")
    )
    db.commit()

    # Create reviews for each org
    db.execute(
        text(
            """
            INSERT INTO reviews (review_id, sku_id, marketplace, rating, text, has_media, org_id)
            VALUES ('rev-a', 100, 'WB', 5, 'Great!', 0, 10)
        """
        )
    )
    db.execute(
        text(
            """
            INSERT INTO reviews (review_id, sku_id, marketplace, rating, text, has_media, org_id)
            VALUES ('rev-b', 200, 'WB', 1, 'Bad!', 0, 20)
        """
        )
    )
    db.commit()

    # Query for org A
    reviews_a = db.execute(text("SELECT review_id FROM reviews WHERE org_id = 10")).fetchall()

    # Query for org B
    reviews_b = db.execute(text("SELECT review_id FROM reviews WHERE org_id = 20")).fetchall()

    # Verify isolation
    assert len(reviews_a) == 1
    assert reviews_a[0][0] == "rev-a"

    assert len(reviews_b) == 1
    assert reviews_b[0][0] == "rev-b"


def test_cross_org_leak_prevented(db: Session):
    """Test that data doesn't leak between orgs."""
    # Create test data
    db.execute(text("INSERT INTO organizations (id, name) VALUES (30, 'Org Secure')"))
    db.commit()

    db.execute(
        text(
            "INSERT INTO sku (marketplace, nm_id, article, org_id) VALUES ('WB', '999', 'SECRET', 30)"
        )
    )
    db.commit()

    # Try to query with wrong org_id
    wrong_org_skus = db.execute(text("SELECT article FROM sku WHERE org_id = 999")).fetchall()

    # Should find nothing
    assert len(wrong_org_skus) == 0


def test_org_credentials_isolation(db: Session):
    """Test that credentials are isolated by org."""
    # Create credentials for org 10
    db.execute(
        text(
            """
            INSERT INTO org_credentials (org_id, wb_feedbacks_token)
            VALUES (10, 'token-for-org-10')
        """
        )
    )
    db.commit()

    # Query credentials for org 10
    creds_10 = db.execute(
        text("SELECT wb_feedbacks_token FROM org_credentials WHERE org_id = 10")
    ).first()

    # Query credentials for org 20 (shouldn't exist)
    creds_20 = db.execute(
        text("SELECT wb_feedbacks_token FROM org_credentials WHERE org_id = 20")
    ).first()

    assert creds_10[0] == "token-for-org-10"
    assert creds_20 is None


def test_org_members_isolation(db: Session):
    """Test that org members are correctly scoped."""
    # Create test users
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (1, 111)"))
    db.execute(text("INSERT INTO users (id, tg_user_id) VALUES (2, 222)"))
    db.commit()

    # Add user 1 to org 10
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (10, 1, 'owner')"))

    # Add user 2 to org 20
    db.execute(text("INSERT INTO org_members (org_id, user_id, role) VALUES (20, 2, 'manager')"))
    db.commit()

    # Query members for org 10
    members_10 = db.execute(text("SELECT user_id FROM org_members WHERE org_id = 10")).fetchall()

    # Query members for org 20
    members_20 = db.execute(text("SELECT user_id FROM org_members WHERE org_id = 20")).fetchall()

    # Verify isolation
    assert len(members_10) == 1
    assert members_10[0][0] == 1

    assert len(members_20) == 1
    assert members_20[0][0] == 2
