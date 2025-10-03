# Stage 19.3 Multi-Tenant Enforcement - PROGRESS REPORT

**Generated**: 2025-10-03
**Status**: IN PROGRESS (60% complete)

## Summary

This report tracks the completion of Stage 19.3: Making the system SAFE for production with complete multi-tenant data isolation.

## ✅ COMPLETED (60%)

### Services (3/10 core services complete)

#### 1. pricing_service.py ✅ COMPLETE
- [x] Added `*, org_id: int` parameter to `compute_pricing_for_skus()`
- [x] Added org_id to SKU query: `.where(SKU.org_id == org_id)`
- [x] Updated `_get_sku_info()` to accept and use org_id
- [x] Added org_id to CostPriceHistory query
- [x] Added org_id when creating PricingAdvice records
- **Location**: app/services/pricing_service.py:77-180

#### 2. reviews_sla.py ✅ COMPLETE
- [x] Added `*, org_id: int` to 3 functions:
  - `update_first_reply_timestamp()`
  - `compute_review_sla()`
  - `find_overdue_reviews()`
- [x] Converted all text() SQL to exec_scoped()
- [x] Added org_id filters to all queries
- [x] Updated reviews_sla.py router to pass org_id
- **Location**: app/services/reviews_sla.py + app/web/routers/reviews_sla.py

#### 3. supply_planner.py + Domain Helpers ✅ COMPLETE
- [x] Added `*, org_id: int` to `generate_supply_plan()`
- [x] Updated `collect_candidates()` with org_id parameter
- [x] Added org_id filters to DailyStock, SKU, Warehouse joins
- [x] Updated `get_current_cost()` with org_id
- [x] Updated `get_latest_stock()` with org_id
- [x] Updated `rolling_sv()` with org_id (domain/supply/demand.py)
- [x] Updated `demand_stdev()` with org_id
- [x] Added org_id when creating AdviceSupply records
- [x] Updated supply.py router to pass org_id
- **Locations**:
  - app/services/supply_planner.py
  - app/domain/supply/constraints.py
  - app/domain/supply/demand.py
  - app/web/routers/supply.py

### Routers (4/11 complete with full SQL scoping)

#### 1. pricing.py ✅ COMPLETE
- [x] Has OrgScope parameter
- [x] Calls compute_pricing_for_skus() with org_id
- [x] Has rate limit enforcement
- **Location**: app/web/routers/pricing.py

#### 2. reviews_sla.py ✅ COMPLETE
- [x] All 4 endpoints have OrgScope
- [x] All calls to service functions pass org_id
- [x] export_sla_csv has org_id filter + uses exec_scoped()
- **Location**: app/web/routers/reviews_sla.py

#### 3. supply.py ✅ COMPLETE
- [x] get_supply_plan() has org_id filters on AdviceSupply, SKU, Warehouse
- [x] compute_supply_plan() calls service with org_id
- **Location**: app/web/routers/supply.py

#### 4. bi_export.py ✅ COMPLETE - ALL 10 ENDPOINTS
- [x] pnl.csv + pnl.xlsx (org_id filter + check_export_limit)
- [x] inventory.csv + inventory.xlsx (org_id filter + check_export_limit)
- [x] supply_advice.csv + supply_advice.xlsx (org_id filter + check_export_limit)
- [x] pricing_advice.csv + pricing_advice.xlsx (org_id filter + check_export_limit)
- [x] reviews_summary.csv + reviews_summary.xlsx (org_id filter + check_export_limit)
- **All queries converted to exec_scoped() with org_id**
- **All endpoints have check_export_limit() enforcement**
- **Location**: app/web/routers/bi_export.py

### Infrastructure ✅ ALL COMPLETE
- [x] OrgScope dependency (app/web/deps.py)
- [x] exec_scoped() validation (app/db/utils.py)
- [x] check_rate_limit() (app/core/limits.py)
- [x] check_export_limit() (app/core/limits.py)
- [x] check_job_queue_limit() (app/core/limits.py)
- [x] tenant_unscoped_query_total metric (app/core/metrics.py)
- [x] Migration 130f3aadec77 (organizations, users, org_members, org_id columns)
- [x] Alembic head verified: 130f3aadec77

## 🔄 IN PROGRESS (0%)

None currently - moving to next tasks

## ⏳ PENDING (40%)

### Services (7 remaining)

#### reviews_service.py - NOT STARTED
- [ ] Add `*, org_id: int` to `build_reply_for_review()`
- [ ] Add org_id filters to SQL/ORM queries
- **Estimated effort**: 15 minutes

#### cashflow_pnl.py - NOT STARTED
- [ ] Add `*, org_id: int` to 4 functions:
  - recompute_pnl()
  - recompute_cashflow()
  - run_scenario()
  - run_reconciliation()
- [ ] Add org_id filters to all SQL/ORM queries
- **Estimated effort**: 45 minutes

#### Other services - TO BE ASSESSED
- [ ] inventory services (if any)
- [ ] advice services (if any)
- [ ] finance services (if any)
- [ ] export services (if any)

### Routers (7 remaining - need SQL filters)

The following routers have OrgScope parameters but missing SQL filters:

#### 1. inventory.py
- [x] Has OrgScope import
- [x] Has org_id parameter
- [ ] Add WHERE org_id filters to SQL queries
- **Status**: 30% complete

#### 2. advice.py
- [x] Has OrgScope import
- [x] Has org_id parameter
- [ ] Add WHERE org_id filters to SQL queries
- **Status**: 30% complete

#### 3. finance.py
- [x] Has OrgScope import
- [x] Has org_id parameter
- [ ] Add WHERE org_id filters to SQL queries
- [ ] Add check_rate_limit() enforcement
- [ ] Add check_job_queue_limit() enforcement
- **Status**: 30% complete

#### 4. export.py
- [x] Has OrgScope import
- [x] Has org_id parameter
- [ ] Add WHERE org_id filters to SQL queries (3 endpoints)
- [ ] Add check_export_limit() enforcement (3 endpoints)
- **Status**: 30% complete

#### 5. dashboard.py
- [x] Has OrgScope parameter
- [ ] Verify all SQL queries have org_id filters
- [ ] Convert any remaining text() to exec_scoped()
- **Status**: 50% complete (may be done)

#### 6. reviews.py
- [x] Has OrgScope parameter
- [ ] Verify all ORM queries have org_id filters
- **Status**: 80% complete (likely done)

#### 7. pricing.py
- [x] Verified complete in previous report
- **Status**: 100% complete

### BI Views - NOT STARTED
- [ ] Audit vw_pnl_daily for org_id column
- [ ] Audit vw_inventory_snapshot for org_id column
- [ ] Audit vw_supply_advice for org_id column
- [ ] Audit vw_pricing_advice for org_id column
- [ ] Audit vw_reviews_summary for org_id column
- [ ] Audit vw_reviews_sla for org_id column
- [ ] Audit vw_cashflow_daily for org_id column
- [ ] Audit vw_pnl_actual_daily for org_id column
- [ ] Audit vw_commission_recon for org_id column
- [ ] Fix cost_price_latest naming inconsistency
- **Estimated effort**: 30 minutes

### Alert Detector - NOT STARTED
- [ ] Create app/ops/detectors.py:check_tenant_unscoped_queries()
- [ ] Query tenant_unscoped_query_total metric
- [ ] Integrate with scheduler ops_health_check()
- [ ] Connect to Telegram alerting
- **Estimated effort**: 20 minutes

### GitHub Actions CI - NOT STARTED
- [ ] Create .github/workflows/ci.yml
- [ ] Add org scope guard step: scripts/ci/check_org_scope.sh
- [ ] Add pytest step
- [ ] Add alembic check step
- **Estimated effort**: 15 minutes

### Tests - NOT STARTED
- [ ] Update test fixtures with org_id
- [ ] Fix service call mocks to pass org_id
- [ ] Fix 4 failing tests
- [ ] Run full pytest suite
- **Estimated effort**: 45 minutes

## Definition of Done (DoD)

### ✅ Completed (5/13)
- [x] pricing_service.py: 10/10 with org_id
- [x] reviews_sla.py: 10/10 with org_id
- [x] supply_planner.py: 10/10 with org_id
- [x] bi_export.py: 10/10 endpoints with org_id + export limits
- [x] Supply domain helpers: org_id scoping

### ⏳ Pending (8/13)
- [ ] Services: 10/10 updated (3/10 done)
- [ ] Export limits: 7/7 endpoints (10/10 done - bi_export complete, export.py pending)
- [ ] Routers: 11/11 with complete SQL filters (4/11 done)
- [ ] BI views: audited and fixed
- [ ] Alert detector: created and integrated
- [ ] GitHub Actions: CI workflow created
- [ ] Tests: all passing
- [ ] Final report: STAGE_19_3_FINAL_ENFORCEMENT.md

## Next Steps (Priority Order)

1. **Audit remaining routers** (inventory, advice, finance, export) - verify SQL filters
2. **Update cashflow_pnl.py service** - add org_id to 4 functions
3. **Update reviews_service.py** - add org_id to build_reply_for_review
4. **Audit BI views** - verify org_id in all views
5. **Create alert detector** - check_tenant_unscoped_queries()
6. **Create GitHub Actions CI** - .github/workflows/ci.yml
7. **Fix tests** - update fixtures and mocks
8. **Final report** - create STAGE_19_3_FINAL_ENFORCEMENT.md

## Safety Status

**Current Status**: NOT SAFE for production

**Reason**:
- 7/10 services incomplete
- 7/11 routers need SQL filter verification
- No alert detector
- No CI guard enabled
- Tests not passing

**Estimated Time to SAFE**: 3-4 hours of focused work

## Files Modified This Session

### Services
- app/services/pricing_service.py
- app/services/reviews_sla.py
- app/services/supply_planner.py

### Domain
- app/domain/supply/constraints.py
- app/domain/supply/demand.py

### Routers
- app/web/routers/bi_export.py (10 endpoints)
- app/web/routers/reviews_sla.py (4 endpoints)
- app/web/routers/supply.py (2 endpoints)

### Scripts
- scripts/update_all_services.py (created)

## Metrics

- **Services updated**: 3/10 (30%)
- **Routers complete**: 4/11 (36%)
- **Export endpoints with limits**: 10/10 BI + 0/3 export.py = 10/13 (77%)
- **BI views audited**: 0/9 (0%)
- **Alert detector**: 0/1 (0%)
- **CI workflow**: 0/1 (0%)
- **Tests fixed**: 0/4 (0%)

**Overall Progress**: 60% infrastructure + services, 40% remaining (routers, views, CI, tests)
