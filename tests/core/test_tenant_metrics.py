"""Tests for tenant scoping metrics (Stage 19 Hardening)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.metrics import tenant_unscoped_query_total
from app.db.utils import exec_scoped


def test_exec_scoped_increments_metric_on_missing_org_id(db: Session) -> None:
    """Test exec_scoped increments metric when org_id is missing."""
    # Get initial counter value
    before = tenant_unscoped_query_total.labels(error_type="missing_org_id")._value.get()

    # Try to execute without org_id
    with pytest.raises(RuntimeError, match="org_id is required"):
        exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id=None)

    # Metric should have incremented
    after = tenant_unscoped_query_total.labels(error_type="missing_org_id")._value.get()
    assert after == before + 1


def test_exec_scoped_increments_metric_on_missing_filter(db: Session) -> None:
    """Test exec_scoped increments metric when SQL doesn't have org_id filter."""
    # Get initial counter value
    before = tenant_unscoped_query_total.labels(error_type="missing_filter")._value.get()

    # Try to execute SQL without org_id in WHERE clause
    with pytest.raises(RuntimeError, match="must contain org_id filter"):
        exec_scoped(db, "SELECT * FROM sku WHERE marketplace = 'WB'", {}, org_id=100)

    # Metric should have incremented
    after = tenant_unscoped_query_total.labels(error_type="missing_filter")._value.get()
    assert after == before + 1


def test_exec_scoped_does_not_increment_on_valid_query(db: Session) -> None:
    """Test exec_scoped does NOT increment metric on valid scoped query."""
    # Get initial counter values
    before_missing_org = tenant_unscoped_query_total.labels(
        error_type="missing_org_id"
    )._value.get()
    before_missing_filter = tenant_unscoped_query_total.labels(
        error_type="missing_filter"
    )._value.get()

    # Execute valid scoped query (may fail if table doesn't exist, but metric shouldn't change)
    try:
        exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id=100)
    except Exception:
        pass  # Ignore execution errors, we're only testing metric behavior

    # Metrics should NOT have changed
    after_missing_org = tenant_unscoped_query_total.labels(error_type="missing_org_id")._value.get()
    after_missing_filter = tenant_unscoped_query_total.labels(
        error_type="missing_filter"
    )._value.get()

    assert after_missing_org == before_missing_org
    assert after_missing_filter == before_missing_filter


def test_metric_tracks_both_error_types_independently(db: Session) -> None:
    """Test metric tracks missing_org_id and missing_filter independently."""
    # Get initial values
    before_org = tenant_unscoped_query_total.labels(error_type="missing_org_id")._value.get()
    before_filter = tenant_unscoped_query_total.labels(error_type="missing_filter")._value.get()

    # Trigger missing_org_id error
    with pytest.raises(RuntimeError):
        exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id=None)

    # Trigger missing_filter error
    with pytest.raises(RuntimeError):
        exec_scoped(db, "SELECT * FROM sku WHERE marketplace = 'WB'", {}, org_id=100)

    # Check both incremented independently
    after_org = tenant_unscoped_query_total.labels(error_type="missing_org_id")._value.get()
    after_filter = tenant_unscoped_query_total.labels(error_type="missing_filter")._value.get()

    assert after_org == before_org + 1
    assert after_filter == before_filter + 1
