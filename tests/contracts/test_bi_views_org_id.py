"""Contract test: all BI views contain org_id column and no NULL org_id.

This test verifies:
1. Each BI view has org_id column (schema check)
2. No rows with NULL org_id exist (data integrity)

This is a regression guard - it will fail if views are modified incorrectly.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

# List of all BI views that MUST have org_id
VIEWS = [
    "vw_pnl_daily",
    "vw_inventory_snapshot",
    "vw_supply_advice",
    "vw_pricing_advice",
    "vw_reviews_summary",
    "vw_cashflow_daily",
    "vw_pnl_actual_daily",
    "vw_commission_recon",
    "vw_reviews_sla",
    "vw_ops_health",
    "vw_slo_daily",
]


@pytest.fixture
def db() -> Session:
    """Get database session for contract tests."""
    from app.web.deps import get_db

    return next(get_db())


@pytest.mark.parametrize("view_name", VIEWS)
def test_view_has_org_id_column(db: Session, view_name: str):
    """Verify view has org_id column (schema check)."""
    try:
        # Try to select org_id column with LIMIT 0 (schema check only)
        result = db.execute(text(f"SELECT org_id FROM {view_name} LIMIT 0"))
        assert result is not None, f"View {view_name} is not selectable"
    except Exception as e:
        pytest.fail(
            f"❌ View {view_name} lacks org_id column or doesn't exist.\n"
            f"Error: {e}\n"
            f"FIX: Add org_id to view definition in migrations."
        )


@pytest.mark.parametrize("view_name", VIEWS)
def test_view_has_no_null_org_id(db: Session, view_name: str):
    """Verify view has no rows with NULL org_id (data integrity)."""
    try:
        # Count rows with NULL org_id
        count_null = db.execute(
            text(f"SELECT COUNT(*) FROM {view_name} WHERE org_id IS NULL")
        ).scalar()

        assert count_null == 0, (
            f"❌ View {view_name} returns {count_null} rows with NULL org_id.\n"
            f"FIX: Ensure view JOIN/WHERE clauses preserve org_id from base tables."
        )
    except Exception as e:
        # If view doesn't exist or query fails, that's caught by schema test
        # But if it's a different error, report it
        if "no such table" not in str(e).lower() and "does not exist" not in str(e).lower():
            pytest.fail(f"❌ View {view_name} NULL check failed: {e}")


def test_all_views_summary(db: Session):
    """Summary test - check all views at once."""
    failures = []
    passed = 0

    for view_name in VIEWS:
        try:
            # Schema check
            db.execute(text(f"SELECT org_id FROM {view_name} LIMIT 0"))

            # NULL check
            count_null = db.execute(
                text(f"SELECT COUNT(*) FROM {view_name} WHERE org_id IS NULL")
            ).scalar()

            if count_null > 0:
                failures.append(f"{view_name}: {count_null} NULL org_id rows")
            else:
                passed += 1

        except Exception as e:
            failures.append(f"{view_name}: {e}")

    # Report results
    total = len(VIEWS)
    print(f"\n{'='*60}")
    print(f"BI Views Org-ID Contract Test Results")
    print(f"{'='*60}")
    print(f"Total views: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(failures)}")

    if failures:
        print(f"\n❌ Failures:")
        for f in failures:
            print(f"  - {f}")

    assert not failures, f"\n❌ {len(failures)}/{total} views failed org_id contract"

    print(f"\n✅ All {total} BI views have org_id column with no NULL values")
