# Stage 19: Org-Scoping Migration Guide

## Overview
All business queries must be scoped to `org_id` from the current user to ensure data isolation between organizations.

## Pattern: SQL Queries (Raw Text)

### Before:
```python
@router.get("/reviews")
def get_reviews(db: DBSession, user: CurrentUser):
    stmt = text("SELECT * FROM reviews WHERE rating >= 4")
    rows = db.execute(stmt).fetchall()
    return rows
```

### After:
```python
from app.web.auth import get_org_scope

@router.get("/reviews")
def get_reviews(
    db: DBSession,
    org_id: int = Depends(get_org_scope),  # Add org scoping
):
    stmt = text("SELECT * FROM reviews WHERE org_id = :org_id AND rating >= 4")
    rows = db.execute(stmt, {"org_id": org_id}).fetchall()
    return rows
```

## Pattern: SQLAlchemy ORM

### Before:
```python
@router.get("/sku")
def get_sku(db: DBSession, user: CurrentUser):
    stmt = select(SKU).where(SKU.marketplace == "WB")
    results = db.execute(stmt).scalars().all()
    return results
```

### After:
```python
from app.web.auth import get_org_scope

@router.get("/sku")
def get_sku(
    db: DBSession,
    org_id: int = Depends(get_org_scope),
):
    stmt = select(SKU).where(
        SKU.org_id == org_id,  # CRITICAL: Add org filter
        SKU.marketplace == "WB",
    )
    results = db.execute(stmt).scalars().all()
    return results
```

## Pattern: Service Layer Functions

### Before:
```python
def compute_metrics(db: Session, date_from: date, date_to: date):
    query = text("""
        SELECT * FROM metrics_daily
        WHERE d BETWEEN :d_from AND :d_to
    """)
    return db.execute(query, {"d_from": date_from, "d_to": date_to}).fetchall()
```

### After:
```python
def compute_metrics(
    db: Session,
    org_id: int,  # Add org_id parameter
    date_from: date,
    date_to: date,
):
    query = text("""
        SELECT * FROM metrics_daily
        WHERE org_id = :org_id  -- Add org filter
            AND d BETWEEN :d_from AND :d_to
    """)
    return db.execute(
        query,
        {"org_id": org_id, "d_from": date_from, "d_to": date_to}
    ).fetchall()
```

## Pattern: Exports (CSV/XLSX)

### Before:
```python
@router.get("/export/sales")
def export_sales(db: DBSession, date_from: date):
    query = text("SELECT * FROM daily_sales WHERE d >= :d_from")
    rows = db.execute(query, {"d_from": date_from}).fetchall()
    # ... CSV generation
```

### After:
```python
from app.core.limits import check_export_limit

@router.get("/export/sales")
def export_sales(
    db: DBSession,
    org_id: int = Depends(get_org_scope),
    date_from: date = Query(...),
):
    # Enforce export limits
    check_export_limit(org_id, requested_rows=10000)

    query = text("""
        SELECT * FROM daily_sales
        WHERE org_id = :org_id AND d >= :d_from
    """)
    rows = db.execute(query, {"org_id": org_id, "d_from": date_from}).fetchall()
    # ... CSV generation
```

## Pattern: Compute Endpoints (Rate Limited)

### Before:
```python
@router.post("/pricing/compute")
def compute_pricing(db: DBSession, user: CurrentUser):
    # ... computation logic
```

### After:
```python
from app.core.limits import check_rate_limit
from app.web.auth import require_org_member

@router.post("/pricing/compute")
def compute_pricing(
    db: DBSession,
    current_user: CurrentUser = Depends(require_org_member("manager")),  # Manager+
):
    # Rate limit check
    check_rate_limit(db, current_user.org_id, "pricing_compute", quota_per_sec=5)

    # Computation with org_id scoping
    # ... pass current_user.org_id to service functions
```

## Files to Update

### Routers (Priority 1 - User-facing):
1. ✅ `app/web/routers/orgs.py` - Already scoped
2. ❌ `app/web/routers/reviews.py` - Add org_id filters
3. ❌ `app/web/routers/dashboard.py` - Add org_id filters
4. ❌ `app/web/routers/inventory.py` - Add org_id filters
5. ❌ `app/web/routers/advice.py` - Add org_id filters
6. ❌ `app/web/routers/supply.py` - Add org_id filters
7. ❌ `app/web/routers/pricing.py` - Add org_id + rate limits
8. ❌ `app/web/routers/export.py` - Add org_id + export limits
9. ❌ `app/web/routers/bi_export.py` - Add org_id + export limits
10. ❌ `app/web/routers/finance.py` - Add org_id filters
11. ❌ `app/web/routers/reviews_sla.py` - Add org_id filters

### Services (Priority 2 - Business logic):
1. ❌ `app/services/pricing_service.py` - Add org_id param
2. ❌ `app/services/supply_planner.py` - Add org_id param
3. ❌ `app/services/cashflow_pnl.py` - Add org_id param
4. ❌ `app/services/reviews_service.py` - Add org_id param
5. ❌ `app/services/reviews_sla.py` - Add org_id param

### Ingestion (Priority 3 - Background jobs):
1. ❌ `app/ingestion/wb_*.py` - Use org credentials
2. ❌ `app/ingestion/ozon_*.py` - Use org credentials
3. ❌ `app/scheduler/jobs.py` - Loop over all orgs

## Checklist

- [ ] All SELECT/UPDATE/DELETE queries have `WHERE org_id = :org_id`
- [ ] All INSERT queries have `org_id` in values
- [ ] Export endpoints use `check_export_limit()`
- [ ] Compute endpoints use `check_rate_limit()`
- [ ] RBAC enforced: viewer (read), manager (compute), owner (admin)
- [ ] Service functions accept `org_id` parameter
- [ ] Ingestion uses `org_credentials` table
- [ ] Tests validate no cross-org data leaks

## Testing Commands

```bash
# Run scoping tests
pytest tests/web/test_org_scoping.py -v

# Verify all queries have org_id
git grep -n "FROM.*WHERE" | grep -v "org_id"  # Should be empty!

# Check for missing org_id in INSERTs
git grep -n "INSERT INTO" | grep -E "(sku|reviews|daily_sales)" | grep -v "org_id"
```

## Critical Security Notes

1. **NEVER** allow org_id to be passed as a request parameter - always use `Depends(get_org_scope)`
2. **ALWAYS** validate user belongs to org_id before returning data
3. **NEVER** expose other org's credentials in API responses
4. **ALWAYS** mask tokens in logs (Stage 4 masking still active)
