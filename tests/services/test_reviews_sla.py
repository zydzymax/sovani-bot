"""Tests for reviews SLA service (Stage 18)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.reviews_sla import (
    compute_review_sla,
    find_overdue_reviews,
    update_first_reply_timestamp,
)


def test_update_first_reply_timestamp_idempotent(db: Session):
    """Test that first_reply_at_utc is set only once (idempotent)."""
    # Create a test review
    db.execute(
        text(
            """
        INSERT INTO reviews (id, review_id, marketplace, sku_id, rating, text, has_media, created_at_utc, reply_status)
        VALUES (1, 'test_review_1', 'WB', 1, 5, 'Great!', 0, :created, NULL)
        """
        ),
        {"created": datetime.now(UTC) - timedelta(hours=2)},
    )
    db.commit()

    first_timestamp = datetime.now(UTC)

    # First update should work
    update_first_reply_timestamp(db, 1, when=first_timestamp, reply_kind="template")

    # Verify set
    result = db.execute(
        text("SELECT first_reply_at_utc, reply_kind FROM reviews WHERE id = 1")
    ).first()
    assert result[0] is not None
    assert result[1] == "template"

    # Second update should not change timestamp (idempotent)
    second_timestamp = datetime.now(UTC) + timedelta(hours=1)
    update_first_reply_timestamp(db, 1, when=second_timestamp, reply_kind="ai")

    result = db.execute(
        text("SELECT first_reply_at_utc, reply_kind FROM reviews WHERE id = 1")
    ).first()
    # Should still be first_timestamp, not second_timestamp
    assert result[0] == first_timestamp
    assert result[1] == "template"  # Kind also unchanged


def test_compute_review_sla_basic(db: Session):
    """Test SLA computation with basic data."""
    now = datetime.now(UTC)

    # Insert test reviews with varying TTFR
    reviews = [
        # Within SLA (< 24h)
        (1, "r1", now - timedelta(hours=48), now - timedelta(hours=36), "template"),  # 12h TTFR
        (2, "r2", now - timedelta(hours=36), now - timedelta(hours=24), "ai"),  # 12h TTFR
        # Outside SLA (> 24h)
        (3, "r3", now - timedelta(hours=72), now - timedelta(hours=24), "ai"),  # 48h TTFR
        # Not replied yet
        (4, "r4", now - timedelta(hours=12), None, None),
    ]

    for review_id, ext_id, created, replied, kind in reviews:
        db.execute(
            text(
                """
            INSERT INTO reviews (id, review_id, marketplace, sku_id, rating, text, has_media, created_at_utc, first_reply_at_utc, reply_kind, reply_status)
            VALUES (:id, :ext_id, 'WB', 1, 5, 'Test', 0, :created, :replied, :kind, CASE WHEN :replied IS NOT NULL THEN 'sent' ELSE NULL END)
            """
            ),
            {
                "id": review_id,
                "ext_id": ext_id,
                "created": created,
                "replied": replied,
                "kind": kind,
            },
        )
    db.commit()

    # Compute SLA
    d_from = now - timedelta(days=3)
    d_to = now
    result = compute_review_sla(db, d_from, d_to)

    assert result["count_total"] == 4
    assert result["replied"] == 3
    assert result["within_sla"] == 2  # First 2 reviews
    assert result["share_within_sla"] == pytest.approx(66.67, rel=0.1)


def test_find_overdue_reviews_priority(db: Session):
    """Test that overdue reviews are sorted by priority correctly."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=15)  # 15 hours ago

    # Insert reviews with different priorities
    reviews = [
        # Priority 1: Negative + AI needed
        (1, "r1", 1, "Long text " * 10, 1, cutoff - timedelta(hours=5)),  # rating=1, ai_needed=True
        # Priority 2: Negative + no AI
        (2, "r2", 2, "Short", 0, cutoff - timedelta(hours=4)),  # rating=2, ai_needed=False
        # Priority 3: Neutral + AI
        (3, "r3", 3, "Long text " * 10, 0, cutoff - timedelta(hours=3)),  # rating=3, ai_needed=True
        # Priority 4: Neutral + no AI
        (4, "r4", 3, "Short", 0, cutoff - timedelta(hours=2)),  # rating=3, ai_needed=False
        # Priority 5: Positive + AI
        (5, "r5", 5, "Long text " * 10, 0, cutoff - timedelta(hours=1)),  # rating=5, ai_needed=True
        # Priority 6: Positive + no AI
        (6, "r6", 4, "Short", 0, cutoff - timedelta(minutes=30)),  # rating=4, ai_needed=False
    ]

    for review_id, ext_id, rating, text, has_media, created in reviews:
        db.execute(
            text(
                """
            INSERT INTO reviews (id, review_id, marketplace, sku_id, rating, text, has_media, created_at_utc, first_reply_at_utc, reply_status)
            VALUES (:id, :ext_id, 'WB', 1, :rating, :text, :has_media, :created, NULL, NULL)
            """
            ),
            {
                "id": review_id,
                "ext_id": ext_id,
                "rating": rating,
                "text": text,
                "has_media": has_media,
                "created": created,
            },
        )
    db.commit()

    # Find overdue
    overdue = find_overdue_reviews(db, now, escalate_after_hours=12, limit=10)

    assert len(overdue) == 6

    # Check priority order
    assert overdue[0]["review_id"] == 1  # Negative + AI
    assert overdue[1]["review_id"] == 2  # Negative + no AI
    assert overdue[2]["review_id"] == 3  # Neutral + AI
    assert overdue[3]["review_id"] == 4  # Neutral + no AI
    assert overdue[4]["review_id"] == 5  # Positive + AI
    assert overdue[5]["review_id"] == 6  # Positive + no AI


def test_find_overdue_reviews_filters(db: Session):
    """Test overdue reviews filters by marketplace and escalate threshold."""
    now = datetime.now(UTC)

    # Insert reviews
    db.execute(
        text(
            """
        INSERT INTO reviews (id, review_id, marketplace, sku_id, rating, text, has_media, created_at_utc, first_reply_at_utc)
        VALUES
        (1, 'wb1', 'WB', 1, 3, 'Test', 0, :old, NULL),
        (2, 'ozon1', 'OZON', 1, 3, 'Test', 0, :old, NULL),
        (3, 'wb2', 'WB', 1, 3, 'Test', 0, :recent, NULL)
        """
        ),
        {
            "old": now - timedelta(hours=15),  # Old enough to escalate
            "recent": now - timedelta(hours=5),  # Too recent
        },
    )
    db.commit()

    # Find overdue with 12h threshold
    overdue = find_overdue_reviews(db, now, escalate_after_hours=12, limit=10)
    assert len(overdue) == 2  # Only reviews 1 and 2 (review 3 is too recent)

    # Filter by marketplace
    overdue_wb = find_overdue_reviews(db, now, escalate_after_hours=12, limit=10, marketplace="WB")
    assert len(overdue_wb) == 1
    assert overdue_wb[0]["marketplace"] == "WB"


def test_compute_review_sla_by_marketplace(db: Session):
    """Test SLA breakdown by marketplace."""
    now = datetime.now(UTC)

    # Insert reviews for different marketplaces
    for i, mp in enumerate(["WB", "OZON"]):
        db.execute(
            text(
                """
            INSERT INTO reviews (id, review_id, marketplace, sku_id, rating, text, has_media, created_at_utc, first_reply_at_utc, reply_kind)
            VALUES (:id, :ext_id, :mp, 1, 5, 'Test', 0, :created, :replied, 'template')
            """
            ),
            {
                "id": i + 1,
                "ext_id": f"r{i}",
                "mp": mp,
                "created": now - timedelta(hours=48),
                "replied": now - timedelta(hours=36),  # 12h TTFR
            },
        )
    db.commit()

    result = compute_review_sla(db, now - timedelta(days=3), now)

    assert len(result["by_marketplace"]) == 2
    assert {mp["marketplace"] for mp in result["by_marketplace"]} == {"WB", "OZON"}


def test_compute_review_sla_by_reply_kind(db: Session):
    """Test SLA breakdown by reply kind (template vs AI)."""
    now = datetime.now(UTC)

    # Insert reviews with different reply kinds
    for i, kind in enumerate(["template", "ai", "template"]):
        db.execute(
            text(
                """
            INSERT INTO reviews (id, review_id, marketplace, sku_id, rating, text, has_media, created_at_utc, first_reply_at_utc, reply_kind)
            VALUES (:id, :ext_id, 'WB', 1, 5, 'Test', 0, :created, :replied, :kind)
            """
            ),
            {
                "id": i + 1,
                "ext_id": f"r{i}",
                "created": now - timedelta(hours=48),
                "replied": now - timedelta(hours=36),
                "kind": kind,
            },
        )
    db.commit()

    result = compute_review_sla(db, now - timedelta(days=3), now)

    assert len(result["by_reply_kind"]) == 2
    kinds_dict = {item["reply_kind"]: item["count"] for item in result["by_reply_kind"]}
    assert kinds_dict["template"] == 2
    assert kinds_dict["ai"] == 1
