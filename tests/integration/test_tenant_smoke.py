"""Tenant isolation smoke tests (Stage 19).

These tests verify that organizations cannot access each other's data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.utils import exec_scoped


def test_tenant_smoke_sku_isolation(db: Session):
    """Smoke test: Org A cannot see Org B's SKUs."""
    # Create orgs
    db.execute(text("INSERT OR IGNORE INTO organizations (id, name) VALUES (100, 'Org A')"))
    db.execute(text("INSERT OR IGNORE INTO organizations (id, name) VALUES (200, 'Org B')"))
    db.commit()

    # Org A creates SKU
    exec_scoped(
        db,
        "INSERT INTO sku (marketplace, nm_id, article, org_id) VALUES ('WB', '11111', 'SKU-A', :org_id)",
        {},
        org_id=100,
    )
    db.commit()

    # Org B creates SKU
    exec_scoped(
        db,
        "INSERT INTO sku (marketplace, nm_id, article, org_id) VALUES ('WB', '22222', 'SKU-B', :org_id)",
        {},
        org_id=200,
    )
    db.commit()

    # Org A queries - should only see SKU-A
    rows_a = exec_scoped(
        db,
        "SELECT article FROM sku WHERE org_id = :org_id",
        {},
        org_id=100,
    ).fetchall()

    assert len(rows_a) == 1
    assert rows_a[0][0] == "SKU-A"

    # Org B queries - should only see SKU-B
    rows_b = exec_scoped(
        db,
        "SELECT article FROM sku WHERE org_id = :org_id",
        {},
        org_id=200,
    ).fetchall()

    assert len(rows_b) == 1
    assert rows_b[0][0] == "SKU-B"


def test_tenant_smoke_reviews_isolation(db: Session):
    """Smoke test: Org A cannot see Org B's reviews."""
    # Setup SKUs
    exec_scoped(
        db,
        "INSERT INTO sku (id, marketplace, nm_id, org_id) VALUES (1000, 'WB', 'nm1', :org_id)",
        {},
        org_id=100,
    )
    exec_scoped(
        db,
        "INSERT INTO sku (id, marketplace, nm_id, org_id) VALUES (2000, 'WB', 'nm2', :org_id)",
        {},
        org_id=200,
    )
    db.commit()

    # Org A creates review
    exec_scoped(
        db,
        """INSERT INTO reviews (review_id, sku_id, marketplace, rating, text, has_media, org_id)
           VALUES ('rev-a', 1000, 'WB', 5, 'Great!', 0, :org_id)""",
        {},
        org_id=100,
    )

    # Org B creates review
    exec_scoped(
        db,
        """INSERT INTO reviews (review_id, sku_id, marketplace, rating, text, has_media, org_id)
           VALUES ('rev-b', 2000, 'WB', 1, 'Bad!', 0, :org_id)""",
        {},
        org_id=200,
    )
    db.commit()

    # Org A queries
    reviews_a = exec_scoped(
        db,
        "SELECT review_id FROM reviews WHERE org_id = :org_id",
        {},
        org_id=100,
    ).fetchall()

    assert len(reviews_a) == 1
    assert reviews_a[0][0] == "rev-a"

    # Org B queries
    reviews_b = exec_scoped(
        db,
        "SELECT review_id FROM reviews WHERE org_id = :org_id",
        {},
        org_id=200,
    ).fetchall()

    assert len(reviews_b) == 1
    assert reviews_b[0][0] == "rev-b"


def test_exec_scoped_missing_org_id(db: Session):
    """Test exec_scoped raises error if org_id not provided."""
    with pytest.raises(RuntimeError, match="org_id is required"):
        exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id=None)


def test_exec_scoped_missing_filter(db: Session):
    """Test exec_scoped raises error if SQL doesn't contain org_id filter."""
    with pytest.raises(RuntimeError, match="must contain org_id filter"):
        exec_scoped(db, "SELECT * FROM sku WHERE marketplace = 'WB'", {}, org_id=100)


def test_exec_scoped_insert_without_org_id(db: Session):
    """Test exec_scoped catches INSERT without org_id."""
    with pytest.raises(RuntimeError, match="must contain org_id"):
        exec_scoped(
            db,
            "INSERT INTO sku (marketplace, nm_id) VALUES ('WB', '99999')",
            {},
            org_id=100,
        )


def test_tenant_smoke_credentials_isolation(db: Session):
    """Smoke test: Org A cannot see Org B's credentials."""
    # Org A credentials
    exec_scoped(
        db,
        """INSERT INTO org_credentials (org_id, wb_feedbacks_token)
           VALUES (:org_id, 'token-a')""",
        {},
        org_id=100,
    )

    # Org B credentials
    exec_scoped(
        db,
        """INSERT INTO org_credentials (org_id, wb_feedbacks_token)
           VALUES (:org_id, 'token-b')""",
        {},
        org_id=200,
    )
    db.commit()

    # Org A retrieves
    creds_a = exec_scoped(
        db,
        "SELECT wb_feedbacks_token FROM org_credentials WHERE org_id = :org_id",
        {},
        org_id=100,
    ).first()

    assert creds_a[0] == "token-a"

    # Org B retrieves
    creds_b = exec_scoped(
        db,
        "SELECT wb_feedbacks_token FROM org_credentials WHERE org_id = :org_id",
        {},
        org_id=200,
    ).first()

    assert creds_b[0] == "token-b"


def test_tenant_smoke_no_cross_org_leak(db: Session):
    """Smoke test: Queries with wrong org_id return empty."""
    # Org A creates data
    exec_scoped(
        db,
        "INSERT INTO sku (marketplace, nm_id, article, org_id) VALUES ('WB', '88888', 'SECRET', :org_id)",
        {},
        org_id=100,
    )
    db.commit()

    # Org B tries to query (should be empty)
    rows = exec_scoped(
        db,
        "SELECT article FROM sku WHERE org_id = :org_id AND nm_id = '88888'",
        {},
        org_id=200,
    ).fetchall()

    assert len(rows) == 0

    # Org 999 (non-existent) tries to query
    rows_999 = exec_scoped(
        db,
        "SELECT article FROM sku WHERE org_id = :org_id",
        {},
        org_id=999,
    ).fetchall()

    assert len(rows_999) == 0
