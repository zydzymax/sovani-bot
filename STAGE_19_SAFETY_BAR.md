# Stage 19: Multi-Tenant Safety Bar

## Overview

Этот документ описывает минимальные защитные меры ("safety bar"), которые предотвращают утечки данных между организациями в multi-tenant системе.

---

## 🛡️ Implemented Protections

### 1. Mandatory Org Scoping (`app/db/utils.py`)

**`exec_scoped()`** - SQL helper с обязательной проверкой:
- ✅ Требует `org_id` параметр
- ✅ Проверяет наличие `org_id` в SQL
- ✅ Автоматически добавляет `org_id` в параметры
- ✅ Логирует и инкрементирует метрику при нарушении

```python
# ✅ CORRECT
rows = exec_scoped(
    db,
    "SELECT * FROM reviews WHERE org_id = :org_id AND rating >= 4",
    {"limit": 10},
    org_id=current_user.org_id
)

# ❌ WILL RAISE RuntimeError
rows = exec_scoped(
    db,
    "SELECT * FROM reviews WHERE rating >= 4",  # Missing org_id!
    {},
    org_id=100
)
```

### 2. Global Guard Dependencies (`app/web/deps.py`)

**`get_org_scope()`** - FastAPI dependency:
- ✅ Возвращает `org_id` из текущего пользователя
- ✅ Требует валидную авторизацию
- ✅ Бросает 403 если нет org scope

```python
from app.web.deps import OrgScope

@router.get("/reviews")
def get_reviews(org_id: OrgScope, db: DBSession):
    # org_id guaranteed to be valid
    rows = exec_scoped(db, "SELECT * FROM reviews WHERE org_id = :org_id", {}, org_id)
    return rows
```

**Type aliases для удобства**:
```python
OrgScope = Annotated[int, Depends(get_org_scope)]
ManagerUser = Annotated[CurrentUser, Depends(require_manager)]
OwnerUser = Annotated[CurrentUser, Depends(require_owner)]
```

### 3. CI Guard Script (`scripts/check_org_scoping.sh`)

Автоматическая проверка в CI/CD:
- ✅ Сканирует все SQL запросы к бизнес-таблицам
- ✅ Fail build если найдены запросы без `org_id`
- ✅ Проверяет INSERT без `org_id`
- ⚠️  Warning для direct `text()` usage

**Usage**:
```bash
./scripts/check_org_scoping.sh

# In CI:
- name: Check org scoping
  run: ./scripts/check_org_scoping.sh
```

### 4. Comprehensive Tests

**Tenant Smoke Tests** (`tests/integration/test_tenant_smoke.py`):
- ✅ SKU isolation
- ✅ Reviews isolation
- ✅ Credentials isolation
- ✅ No cross-org leaks
- ✅ exec_scoped() validation

**Limits Tests** (`tests/integration/test_tenant_limits.py`):
- ✅ Export limit enforcement
- ✅ Rate limit enforcement
- ✅ Per-org isolation
- ✅ Per-key isolation

---

## 🔧 Implementation Pattern

### Router Pattern

**Before (unsafe)**:
```python
@router.get("/reviews")
def get_reviews(db: DBSession):
    sql = "SELECT * FROM reviews WHERE rating >= 4"
    rows = db.execute(text(sql)).fetchall()
    return rows
```

**After (safe)**:
```python
from app.web.deps import OrgScope
from app.db.utils import exec_scoped

@router.get("/reviews")
def get_reviews(org_id: OrgScope, db: DBSession):
    sql = "SELECT * FROM reviews WHERE org_id = :org_id AND rating >= 4"
    rows = exec_scoped(db, sql, {}, org_id).mappings().all()
    return [dict(r) for r in rows]
```

### Service Pattern

**Before (unsafe)**:
```python
def list_reviews(db: Session, limit: int = 50):
    sql = "SELECT * FROM reviews ORDER BY created_at_utc DESC LIMIT :lim"
    return db.execute(text(sql), {"lim": limit}).fetchall()
```

**After (safe)**:
```python
from app.db.utils import exec_scoped

def list_reviews(db: Session, *, org_id: int, limit: int = 50):
    sql = """
        SELECT * FROM reviews
        WHERE org_id = :org_id
        ORDER BY created_at_utc DESC
        LIMIT :lim
    """
    return exec_scoped(db, sql, {"lim": limit}, org_id).mappings().all()
```

### Compute Endpoint Pattern (with rate limit)

```python
from app.web.deps import OrgScope, ManagerUser
from app.core.limits import check_rate_limit
from app.core.config import get_settings

@router.post("/pricing/compute")
def compute_pricing(
    org_id: OrgScope,
    user: ManagerUser,  # Manager or owner required
    db: DBSession,
):
    settings = get_settings()

    # Rate limit check
    check_rate_limit(db, org_id, "pricing_compute", settings.org_rate_limit_rps)

    # Business logic with org scoping
    sql = """
        SELECT * FROM sku
        WHERE org_id = :org_id AND marketplace = 'WB'
    """
    skus = exec_scoped(db, sql, {}, org_id).fetchall()

    # ... compute pricing
    return {"status": "computed", "sku_count": len(skus)}
```

### Export Endpoint Pattern (with export limit)

```python
from app.web.deps import OrgScope
from app.core.limits import check_export_limit
from app.core.config import get_settings

@router.get("/export/sales.csv")
def export_sales(
    org_id: OrgScope,
    limit: int = Query(5000),
    db: DBSession,
):
    settings = get_settings()

    # Export limit check
    check_export_limit(org_id, limit, settings.org_export_max_rows)

    # Scoped query
    sql = """
        SELECT * FROM daily_sales
        WHERE org_id = :org_id
        ORDER BY d DESC, sku_id
        LIMIT :lim
    """
    rows = exec_scoped(db, sql, {"lim": limit}, org_id).fetchall()

    # ... generate CSV
    return StreamingResponse(...)
```

---

## 🚨 Critical Rules

### ❌ NEVER

1. **Never skip org_id filter**:
   ```python
   # ❌ WRONG
   sql = "SELECT * FROM reviews WHERE rating >= 4"
   ```

2. **Never use direct `text()` without `exec_scoped()`**:
   ```python
   # ❌ WRONG
   db.execute(text("SELECT * FROM sku"), {})
   ```

3. **Never trust org_id from request params**:
   ```python
   # ❌ WRONG
   @router.get("/reviews")
   def get_reviews(org_id: int = Query(...)):  # User can manipulate!
       ...
   ```

4. **Never use `exec_unscoped()` for business queries**:
   ```python
   # ❌ WRONG (only for admin/system queries)
   exec_unscoped(db, "SELECT * FROM reviews", {})
   ```

### ✅ ALWAYS

1. **Always use `OrgScope` dependency**:
   ```python
   # ✅ CORRECT
   @router.get("/reviews")
   def get_reviews(org_id: OrgScope, db: DBSession):
       ...
   ```

2. **Always use `exec_scoped()` for business queries**:
   ```python
   # ✅ CORRECT
   exec_scoped(db, "SELECT * FROM sku WHERE org_id = :org_id", {}, org_id)
   ```

3. **Always include `org_id` in WHERE clause**:
   ```python
   # ✅ CORRECT
   sql = "SELECT * FROM reviews WHERE org_id = :org_id AND rating >= 4"
   ```

4. **Always pass `org_id` to service functions**:
   ```python
   # ✅ CORRECT
   def compute_metrics(db: Session, *, org_id: int, date_from: date):
       ...
   ```

---

## 📋 Checklist: Updating Existing Code

### For Each Router (`app/web/routers/*.py`):

- [ ] Add `org_id: OrgScope` parameter
- [ ] Replace `db.execute(text(...))` with `exec_scoped(...)`
- [ ] Add `WHERE org_id = :org_id` to all SELECT/UPDATE/DELETE
- [ ] Add `org_id` column to all INSERT
- [ ] Add rate limits for compute endpoints
- [ ] Add export limits for export endpoints
- [ ] Add RBAC checks (`ManagerUser`, `OwnerUser`)

### For Each Service (`app/services/*.py`):

- [ ] Add `*, org_id: int` parameter to public functions
- [ ] Replace `db.execute(text(...))` with `exec_scoped(...)`
- [ ] Add `WHERE org_id = :org_id` to all queries
- [ ] Update callers to pass `org_id`

### For Each Test:

- [ ] Add isolation test (org A ≠ org B)
- [ ] Test exec_scoped() validation
- [ ] Test RBAC enforcement
- [ ] Test limits enforcement

---

## 🔍 Verification Commands

### Run CI guard:
```bash
./scripts/check_org_scoping.sh
```

### Run tenant smoke tests:
```bash
pytest tests/integration/test_tenant_smoke.py -v
pytest tests/integration/test_tenant_limits.py -v
```

### Manual grep for unscoped queries:
```bash
# Find SELECTs without org_id
git grep -nE "SELECT .* FROM (reviews|sku|daily_sales)" app/web app/services | grep -v "org_id"

# Find INSERTs without org_id
git grep -nE "INSERT INTO (reviews|sku|daily_sales)" app/web app/services | grep -v "org_id"

# Find direct text() usage
git grep -n "db.execute(text(" app/web app/services | grep -v "exec_scoped"
```

---

## 📊 Metrics & Observability

### Prometheus Metrics

**`errors_total{error_type="missing_org_id"}`**:
- Tracks calls to `exec_scoped()` without org_id
- Alert: > 0 in 5 minutes → CRITICAL

**`errors_total{error_type="unscoped_query"}`**:
- Tracks SQL queries without org_id filter
- Alert: > 0 in 5 minutes → CRITICAL

### Logs

All `exec_scoped()` errors logged at ERROR level:
```json
{
  "level": "ERROR",
  "message": "Unscoped SQL detected (missing org_id): SELECT * FROM reviews...",
  "component": "db_utils"
}
```

---

## 🎯 Priority Routers to Update

### High Priority (User-Facing):
1. ✅ `app/web/routers/orgs.py` - Already scoped
2. ❌ `app/web/routers/reviews.py` - Add org_id filters
3. ❌ `app/web/routers/dashboard.py` - Add org_id filters
4. ❌ `app/web/routers/inventory.py` - Add org_id filters

### Medium Priority (Compute):
5. ❌ `app/web/routers/pricing.py` - Add org_id + rate limits
6. ❌ `app/web/routers/supply.py` - Add org_id + rate limits
7. ❌ `app/web/routers/finance.py` - Add org_id filters

### Low Priority (Export):
8. ❌ `app/web/routers/export.py` - Add org_id + export limits
9. ❌ `app/web/routers/bi_export.py` - Add org_id + export limits

---

## 🚀 Quick Start Guide

### 1. Update a Router

```python
# Import helpers
from app.web.deps import OrgScope, DBSession
from app.db.utils import exec_scoped

# Add org_id parameter
@router.get("/my-endpoint")
def my_endpoint(org_id: OrgScope, db: DBSession):
    # Use exec_scoped for all queries
    sql = "SELECT * FROM my_table WHERE org_id = :org_id"
    rows = exec_scoped(db, sql, {}, org_id).fetchall()
    return rows
```

### 2. Update a Service

```python
from app.db.utils import exec_scoped

def my_service_function(db: Session, *, org_id: int, param: str):
    sql = "SELECT * FROM my_table WHERE org_id = :org_id AND param = :param"
    return exec_scoped(db, sql, {"param": param}, org_id).fetchall()
```

### 3. Run Tests

```bash
pytest tests/integration/test_tenant_smoke.py -v
./scripts/check_org_scoping.sh
```

---

## ✅ Success Criteria

- [ ] All routers use `OrgScope` dependency
- [ ] All services accept `org_id` parameter
- [ ] All SQL queries use `exec_scoped()`
- [ ] All SQL queries contain `WHERE org_id = :org_id`
- [ ] CI guard passes (`./scripts/check_org_scoping.sh`)
- [ ] All tenant smoke tests pass
- [ ] No `errors_total{error_type="unscoped_query"}` in production

---

## 📚 Additional Resources

- `STAGE_19_REPORT.md` - Full implementation report
- `STAGE_19_SCOPING_GUIDE.md` - Detailed migration patterns
- `app/db/utils.py` - exec_scoped() implementation
- `app/web/deps.py` - get_org_scope() implementation
- `tests/integration/test_tenant_smoke.py` - Isolation tests

---

**Remember**: Safety over speed. It's better to block a feature temporarily than to leak data between orgs. 🛡️
