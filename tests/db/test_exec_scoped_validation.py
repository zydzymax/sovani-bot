"""Tests for exec_scoped() validation logic (Stage 19 Hardening)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.utils import exec_scoped, exec_unscoped


def test_exec_scoped_requires_org_id(db: Session) -> None:
    """Test exec_scoped raises error when org_id is None."""
    with pytest.raises(RuntimeError, match="org_id is required"):
        exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id=None)


def test_exec_scoped_requires_org_id_in_sql(db: Session) -> None:
    """Test exec_scoped raises error when SQL doesn't contain org_id."""
    with pytest.raises(RuntimeError, match="must contain org_id filter"):
        exec_scoped(db, "SELECT * FROM sku WHERE marketplace = 'WB'", {}, org_id=100)


def test_exec_scoped_accepts_valid_select(db: Session) -> None:
    """Test exec_scoped accepts SELECT with org_id filter."""
    # Should not raise (may fail on execution if table doesn't exist, but validation passes)
    try:
        exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id=100)
    except RuntimeError as e:
        # If it's our validation error, fail
        if "org_id is required" in str(e) or "must contain org_id" in str(e):
            pytest.fail(f"Validation failed unexpectedly: {e}")
        # Otherwise it's DB execution error, which is OK for this test


def test_exec_scoped_accepts_valid_insert(db: Session) -> None:
    """Test exec_scoped accepts INSERT with org_id column."""
    try:
        exec_scoped(
            db,
            "INSERT INTO sku (marketplace, nm_id, org_id) VALUES ('WB', '123', :org_id)",
            {},
            org_id=100,
        )
    except RuntimeError as e:
        if "org_id is required" in str(e) or "must contain org_id" in str(e):
            pytest.fail(f"Validation failed unexpectedly: {e}")


def test_exec_scoped_rejects_insert_without_org_id(db: Session) -> None:
    """Test exec_scoped rejects INSERT without org_id column."""
    with pytest.raises(RuntimeError, match="must contain org_id"):
        exec_scoped(
            db,
            "INSERT INTO sku (marketplace, nm_id) VALUES ('WB', '123')",
            {},
            org_id=100,
        )


def test_exec_scoped_accepts_update_with_org_id(db: Session) -> None:
    """Test exec_scoped accepts UPDATE with org_id filter."""
    try:
        exec_scoped(
            db,
            "UPDATE sku SET nm_id = '456' WHERE org_id = :org_id AND id = 1",
            {},
            org_id=100,
        )
    except RuntimeError as e:
        if "org_id is required" in str(e) or "must contain org_id" in str(e):
            pytest.fail(f"Validation failed unexpectedly: {e}")


def test_exec_scoped_rejects_update_without_org_id(db: Session) -> None:
    """Test exec_scoped rejects UPDATE without org_id filter."""
    with pytest.raises(RuntimeError, match="must contain org_id"):
        exec_scoped(db, "UPDATE sku SET nm_id = '456' WHERE id = 1", {}, org_id=100)


def test_exec_scoped_accepts_delete_with_org_id(db: Session) -> None:
    """Test exec_scoped accepts DELETE with org_id filter."""
    try:
        exec_scoped(
            db,
            "DELETE FROM sku WHERE org_id = :org_id AND id = 1",
            {},
            org_id=100,
        )
    except RuntimeError as e:
        if "org_id is required" in str(e) or "must contain org_id" in str(e):
            pytest.fail(f"Validation failed unexpectedly: {e}")


def test_exec_scoped_rejects_delete_without_org_id(db: Session) -> None:
    """Test exec_scoped rejects DELETE without org_id filter."""
    with pytest.raises(RuntimeError, match="must contain org_id"):
        exec_scoped(db, "DELETE FROM sku WHERE id = 1", {}, org_id=100)


def test_exec_scoped_merges_org_id_into_params(db: Session) -> None:
    """Test exec_scoped automatically adds org_id to params."""
    # We can't easily test the merged params without executing, but we can verify
    # that valid SQL doesn't raise validation errors
    try:
        exec_scoped(
            db,
            "SELECT * FROM sku WHERE org_id = :org_id AND marketplace = :mp",
            {"mp": "WB"},
            org_id=100,
        )
    except RuntimeError as e:
        if "org_id is required" in str(e) or "must contain org_id" in str(e):
            pytest.fail(f"Validation failed unexpectedly: {e}")


def test_exec_scoped_case_insensitive_org_id_check(db: Session) -> None:
    """Test exec_scoped detects org_id in any case."""
    # Should accept ORG_ID, Org_Id, etc.
    try:
        exec_scoped(db, "SELECT * FROM sku WHERE ORG_ID = :org_id", {}, org_id=100)
    except RuntimeError as e:
        if "org_id is required" in str(e) or "must contain org_id" in str(e):
            pytest.fail(f"Validation failed for uppercase ORG_ID: {e}")


def test_exec_scoped_accepts_complex_where_clause(db: Session) -> None:
    """Test exec_scoped accepts complex WHERE with org_id."""
    try:
        exec_scoped(
            db,
            """
            SELECT * FROM sku
            WHERE org_id = :org_id
            AND marketplace = 'WB'
            AND (rating >= 4 OR has_media = 1)
            """,
            {},
            org_id=100,
        )
    except RuntimeError as e:
        if "org_id is required" in str(e) or "must contain org_id" in str(e):
            pytest.fail(f"Validation failed for complex WHERE: {e}")


def test_exec_scoped_rejects_org_id_in_select_only(db: Session) -> None:
    """Test exec_scoped requires org_id in WHERE, not just SELECT."""
    with pytest.raises(RuntimeError, match="must contain org_id"):
        # org_id in SELECT list but not in WHERE clause
        exec_scoped(db, "SELECT org_id FROM sku WHERE marketplace = 'WB'", {}, org_id=100)


def test_exec_unscoped_allows_unscoped_queries(db: Session) -> None:
    """Test exec_unscoped allows queries without org_id (admin/system use)."""
    # Should not raise validation errors
    try:
        exec_unscoped(db, "SELECT * FROM sku WHERE marketplace = 'WB'", {})
    except RuntimeError as e:
        if "org_id" in str(e):
            pytest.fail(f"exec_unscoped should allow unscoped queries: {e}")


def test_exec_scoped_logs_error_on_missing_org_id(db: Session, caplog) -> None:
    """Test exec_scoped logs error when org_id is missing."""
    with pytest.raises(RuntimeError):
        exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id=None)

    # Check logs
    assert any("exec_scoped called without org_id" in record.message for record in caplog.records)


def test_exec_scoped_logs_error_on_missing_filter(db: Session, caplog) -> None:
    """Test exec_scoped logs error when SQL missing org_id filter."""
    with pytest.raises(RuntimeError):
        exec_scoped(db, "SELECT * FROM sku WHERE marketplace = 'WB'", {}, org_id=100)

    # Check logs
    assert any("Unscoped SQL detected" in record.message for record in caplog.records)


def test_exec_unscoped_logs_warning(db: Session, caplog) -> None:
    """Test exec_unscoped logs warning (use sparingly)."""
    try:
        exec_unscoped(db, "SELECT * FROM sku", {})
    except Exception:
        pass  # Ignore execution errors

    # Check logs
    assert any(
        "exec_unscoped called" in record.message and "use with caution" in record.message
        for record in caplog.records
    )
