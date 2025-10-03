"""Tests for org limits and quotas (Stage 19)."""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.limits import check_export_limit, check_rate_limit


def test_rate_limit_within_quota(db: Session):
    """Test rate limit passes when within quota."""
    org_id = 100

    # Should pass for first N requests
    for i in range(5):
        check_rate_limit(db, org_id, "test_key", quota_per_sec=10)

    # Verify state was created
    result = db.execute(
        text(
            """
            SELECT count FROM org_limits_state
            WHERE org_id = :org_id AND limit_key = 'test_key'
        """
        ),
        {"org_id": org_id},
    ).first()

    assert result is not None
    assert result[0] == 5


def test_rate_limit_exceeds_quota(db: Session):
    """Test rate limit raises HTTPException when quota exceeded."""
    org_id = 101

    # Fill quota
    for i in range(3):
        check_rate_limit(db, org_id, "test_quota", quota_per_sec=3)

    # Next request should fail
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(db, org_id, "test_quota", quota_per_sec=3)

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail


def test_rate_limit_resets_per_second(db: Session):
    """Test rate limit resets in new time bucket."""
    org_id = 102

    # Fill quota in current second
    for i in range(5):
        check_rate_limit(db, org_id, "test_reset", quota_per_sec=5)

    # Wait for new second
    time.sleep(1.1)

    # Should work again in new bucket
    check_rate_limit(db, org_id, "test_reset", quota_per_sec=5)

    # Verify we have 2 time buckets
    result = db.execute(
        text(
            """
            SELECT COUNT(DISTINCT ts_bucket) FROM org_limits_state
            WHERE org_id = :org_id AND limit_key = 'test_reset'
        """
        ),
        {"org_id": org_id},
    ).scalar()

    assert result == 2


def test_export_limit_within_quota():
    """Test export limit passes when within quota."""
    org_id = 200

    # Should pass for reasonable size
    check_export_limit(org_id, requested_rows=1000, max_rows=10000)


def test_export_limit_exceeds_quota():
    """Test export limit raises HTTPException when exceeded."""
    org_id = 201

    with pytest.raises(HTTPException) as exc_info:
        check_export_limit(org_id, requested_rows=200000, max_rows=100000)

    assert exc_info.value.status_code == 400
    assert "Export row limit exceeded" in exc_info.value.detail


def test_export_limit_exact_quota():
    """Test export limit at exact quota boundary."""
    org_id = 202

    # Should pass at exact limit
    check_export_limit(org_id, requested_rows=10000, max_rows=10000)

    # Should fail just over limit
    with pytest.raises(HTTPException):
        check_export_limit(org_id, requested_rows=10001, max_rows=10000)


def test_rate_limit_different_keys(db: Session):
    """Test rate limits are independent per key."""
    org_id = 103

    # Fill quota for key A
    for i in range(5):
        check_rate_limit(db, org_id, "key_a", quota_per_sec=5)

    # Key B should still work
    check_rate_limit(db, org_id, "key_b", quota_per_sec=5)

    # Key A should be full
    with pytest.raises(HTTPException):
        check_rate_limit(db, org_id, "key_a", quota_per_sec=5)


def test_rate_limit_different_orgs(db: Session):
    """Test rate limits are independent per org."""
    # Fill quota for org 104
    for i in range(3):
        check_rate_limit(db, 104, "shared_key", quota_per_sec=3)

    # Org 105 should have independent quota
    check_rate_limit(db, 105, "shared_key", quota_per_sec=3)
    check_rate_limit(db, 105, "shared_key", quota_per_sec=3)
    check_rate_limit(db, 105, "shared_key", quota_per_sec=3)

    # Org 104 should still be full
    with pytest.raises(HTTPException):
        check_rate_limit(db, 104, "shared_key", quota_per_sec=3)


def test_rate_limit_cleanup(db: Session):
    """Test old rate limit buckets are cleaned up."""
    org_id = 106

    # Create old bucket manually
    old_bucket = int(time.time()) - 400  # 6+ minutes ago
    db.execute(
        text(
            """
            INSERT INTO org_limits_state (org_id, limit_key, ts_bucket, count)
            VALUES (:org_id, 'old_key', :bucket, 5)
        """
        ),
        {"org_id": org_id, "bucket": old_bucket},
    )
    db.commit()

    # Trigger cleanup by making new request
    check_rate_limit(db, org_id, "new_key", quota_per_sec=10)

    # Old bucket should be deleted
    old_result = db.execute(
        text(
            """
            SELECT count FROM org_limits_state
            WHERE ts_bucket = :bucket
        """
        ),
        {"bucket": old_bucket},
    ).first()

    assert old_result is None
