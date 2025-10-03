"""Tenant limits integration tests (Stage 19)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.limits import check_export_limit, check_rate_limit


def test_export_limit_enforced(db: Session):
    """Test export limit blocks large requests."""
    org_id = 300

    # Should pass for small export
    check_export_limit(org_id, requested_rows=1000, max_rows=10000)

    # Should fail for large export
    with pytest.raises(HTTPException) as exc_info:
        check_export_limit(org_id, requested_rows=50000, max_rows=10000)

    assert exc_info.value.status_code == 400
    assert "Export row limit exceeded" in exc_info.value.detail
    assert "50000" in exc_info.value.detail
    assert "10000" in exc_info.value.detail


def test_rate_limit_enforced(db: Session):
    """Test rate limit blocks rapid requests."""
    org_id = 301

    # Fill quota
    for i in range(5):
        check_rate_limit(db, org_id, "test_compute", quota_per_sec=5)

    # Next request should fail
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(db, org_id, "test_compute", quota_per_sec=5)

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
    assert "5 requests/second" in exc_info.value.detail


def test_limits_isolated_per_org(db: Session):
    """Test limits are isolated between orgs."""
    # Org A fills quota
    for i in range(3):
        check_rate_limit(db, 302, "shared_endpoint", quota_per_sec=3)

    # Org A should be blocked
    with pytest.raises(HTTPException):
        check_rate_limit(db, 302, "shared_endpoint", quota_per_sec=3)

    # Org B should still have quota
    check_rate_limit(db, 303, "shared_endpoint", quota_per_sec=3)
    check_rate_limit(db, 303, "shared_endpoint", quota_per_sec=3)


def test_export_limit_boundary(db: Session):
    """Test export limit at exact boundary."""
    org_id = 304

    # Exactly at limit - should pass
    check_export_limit(org_id, requested_rows=10000, max_rows=10000)

    # One over limit - should fail
    with pytest.raises(HTTPException):
        check_export_limit(org_id, requested_rows=10001, max_rows=10000)


def test_rate_limit_per_key(db: Session):
    """Test rate limits are independent per key."""
    org_id = 305

    # Fill quota for key A
    for i in range(3):
        check_rate_limit(db, org_id, "pricing_compute", quota_per_sec=3)

    # Key A blocked
    with pytest.raises(HTTPException):
        check_rate_limit(db, org_id, "pricing_compute", quota_per_sec=3)

    # Key B should still work
    check_rate_limit(db, org_id, "supply_compute", quota_per_sec=3)
