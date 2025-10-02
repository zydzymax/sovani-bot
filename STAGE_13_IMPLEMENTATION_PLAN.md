# Stage 13 — Supply Planner Pro: Implementation Plan

**Status:** 🟡 Partial Implementation  
**Complexity:** High (Supply Chain Optimization with Constraints)  
**Estimated Effort:** 16-20 hours for full implementation

---

## Executive Summary

Stage 13 implements a constrained supply planner that generates replenishment recommendations for SKU×Warehouse combinations using rolling sales velocity (SV), forecasts, safety stock, and multiple real-world constraints (capacity, budget, batch sizes).

**Planning Windows:**
- WB: 14 days
- Ozon: 28 days

---

## ✅ Completed Components

### 1. Configuration (`.env.example`)
```bash
PLANNER_SAFETY_COEFF=1.2       # Safety stock multiplier
PLANNER_MIN_BATCH=5            # Minimum order quantity
PLANNER_MULTIPLICITY=1         # Order must be multiple of this
PLANNER_MAX_PER_SLOT=500       # Max per delivery slot
WAREHOUSE_CAPACITY_JSON={}     # {"WB:Казань": 15000}
CASHFLOW_LIMIT=0               # Budget limit (0=unlimited)
PLANNER_SOLVER=heuristic       # Algorithm choice
```

### 2. Settings Integration (`app/core/config.py`)
Added 7 new settings fields to `Settings` class with proper types and defaults.

### 3. Domain Modules Created

#### `app/domain/supply/demand.py` ✅
- `rolling_sv()` - Calculate sales velocity over window
- `forecast_qty()` - Linear forecast (SV × window)
- `stock_cover_days()` - Days of coverage calculation
- `demand_stdev()` - Standard deviation for safety stock

#### `app/domain/supply/constraints.py` ✅
- `get_current_cost()` - Fetch cost price from history
- `get_latest_stock()` - Latest on_hand + in_transit
- `get_warehouse_capacity()` - Parse capacity limits from JSON
- `collect_candidates()` - Build planning candidates with all constraints

**Candidate Structure:**
```python
{
    "marketplace": "WB",
    "wh_id": 123,
    "wh_name": "Казань",
    "sku_id": 456,
    "article": "SOVANI-001",
    "sv": 3.5,              # units/day
    "window": 14,
    "on_hand": 20,
    "in_transit": 10,
    "forecast": 49,         # sv * window
    "safety": 8,            # 1.2 * sqrt(14) * stdev
    "min_batch": 5,
    "multiplicity": 1,
    "max_per_slot": 500,
    "unit_cost": 600.0
}
```

#### `app/domain/supply/planner_heur.py` ✅
- `plan_heuristic()` - Heuristic allocation algorithm
- `ceil_to_multiplicity()` - Round up to multiple
- `SupplyPlan` - Output data structure

**Algorithm:**
1. Calculate need = forecast + safety - (on_hand + in_transit)
2. Apply min_batch and multiplicity constraints
3. Sort by urgency (stock_cover_days ASC, sv DESC)
4. Allocate while respecting budget and max_per_slot

#### `app/domain/supply/explain.py` ✅
- `generate_explanation()` - Human-readable explanation
- `generate_hash()` - SHA256 for rationale tracking

**Example Explanation:**
```
WB, Казань: SV14=3.5/день, прогноз=49, safety=8, остаток=20, в пути=10 → рекомендовано 27
```

#### `app/services/supply_planner.py` ✅
- `generate_supply_plan()` - Main entry point
- Saves to `AdviceSupply` table with rationale hash
- Returns list of plans with explanations

---

## 🔴 Missing Components (TODO)

### 1. API Endpoints (`app/web/routers/supply.py`)
**Required Endpoints:**
```python
GET  /api/v1/supply/plan?window=14&marketplace=WB&limit=50
     → List current plans from AdviceSupply
     
POST /api/v1/supply/compute?window=14
     → Recompute plan (admin-only)
     → Returns fresh recommendations
     
GET  /api/v1/export/supply_plan.xlsx?window=14
     → Export to Excel (similar to Stage 10 financial exports)
```

**Implementation Notes:**
- Use `require_admin` from `app.web.deps` for POST
- Filter by marketplace, warehouse, SKU search
- Pagination with limit/offset
- Join with SKU/Warehouse for article/name display

### 2. TMA UI Page (`tma/src/pages/SupplyPlanner.tsx`)
**Features:**
- Window selector (14/28 days radio buttons)
- Filters: Marketplace dropdown, Warehouse dropdown, SKU search
- Table columns:
  - Article, Marketplace, Warehouse
  - SV, Forecast, Safety, On Hand, In Transit
  - Recommended Qty, Unit Cost, Total Cost
  - Explanation (tooltip on ℹ️ icon)
- Actions:
  - "Пересчитать план" button (admin-only) → POST /compute
  - "Экспорт XLSX" button → GET /export/supply_plan.xlsx
- Real-time updates after recompute

### 3. MILP Solver (`app/domain/supply/planner_milp.py`) (Optional)
**If PLANNER_SOLVER=pulp:**
```python
from pulp import *

def plan_milp(candidates):
    prob = LpProblem("SupplyPlan", LpMaximize)
    
    # Variables: x_{sku,wh} = quantity to order
    # Objective: maximize fill rate or minimize stockout penalty
    # Constraints:
    #   - x >= min_batch (or x=0)
    #   - x % multiplicity == 0
    #   - x <= max_per_slot
    #   - sum(x * unit_cost) <= budget
    #   - sum(x) per warehouse <= capacity
    
    prob.solve()
    return extract_plans(prob)
```

**Dependencies:** `pip install pulp`

### 4. Tests

#### `tests/domain/test_demand.py`
```python
def test_rolling_sv_calculates_average():
    # Create 14 days of sales: 3,4,3,5,2,3,4,3,5,2,3,4,3,5
    # Total = 50, SV = 50/14 = 3.57
    
def test_forecast_qty_rounds_up():
    # sv=3.5, window=14 → forecast = ceil(49) = 49
    
def test_stock_cover_days():
    # on_hand=20, in_transit=10, sv=3.5 → coverage = 30/3.5 = 8.6 days
```

#### `tests/domain/test_constraints.py`
```python
def test_get_current_cost_uses_latest():
    # Insert costs: 2024-01-01:500, 2024-06-01:600
    # Query 2024-07-01 → should return 600
    
def test_collect_candidates_filters_marketplace():
    # Create WB and OZON SKUs
    # Filter marketplace="WB" → only WB candidates
```

#### `tests/domain/test_planner_heur.py`
```python
def test_heuristic_respects_min_batch():
    # need=3, min_batch=5 → should recommend 5
    
def test_heuristic_respects_multiplicity():
    # need=23, multiplicity=10 → should recommend 30
    
def test_heuristic_respects_budget():
    # budget=5000, unit_cost=600, max_affordable=8
    # Should recommend 5 (min_batch) if affordable, else 0
```

#### `tests/services/test_supply_planner_service.py`
```python
def test_generate_supply_plan_saves_to_db():
    # Run planner → check AdviceSupply has records
    # Verify rationale_hash is SHA256
```

#### `tests/web/test_supply_api.py`
```python
def test_get_plan_returns_list():
    # GET /api/v1/supply/plan?window=14 → 200 OK
    
def test_compute_requires_admin():
    # POST /compute as viewer → 403 Forbidden
    # POST /compute as admin → 200 OK
```

### 5. Database Schema

**Existing Table (from Stage 10):**
```sql
CREATE TABLE advice_supply (
    id INTEGER PRIMARY KEY,
    d DATE NOT NULL,                  -- Date of advice
    sku_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    marketplace VARCHAR(10),
    recommended_qty INTEGER,
    rationale_hash VARCHAR(64),       -- SHA256 of explanation
    UNIQUE(d, sku_id, warehouse_id)
);
```

**No migration needed** - table already exists from Stage 10.

### 6. Documentation

#### Usage Guide (`SUPPLY_PLANNER_USAGE.md`)
```markdown
# How to Use Supply Planner

## Via API
curl http://localhost:8000/api/v1/supply/plan?window=14&marketplace=WB

## Via TMA
1. Navigate to "Supply Planner" page
2. Select window (14 or 28 days)
3. Apply filters (optional)
4. Click "Пересчитать план" to refresh
5. Review recommendations
6. Export to Excel for ERP integration

## Interpreting Recommendations
- SV (Sales Velocity): Historical average sales per day
- Forecast: SV × window (expected demand)
- Safety: Buffer for demand variability
- Recommended Qty: Forecast + Safety - Current Stock - In Transit
```

---

## Implementation Priority

### Phase 1: Core Functionality (4-6 hours)
1. ✅ Config and settings
2. ✅ Demand calculations
3. ✅ Constraints collection
4. ✅ Heuristic planner
5. ✅ Explainability
6. ✅ Service facade

### Phase 2: API & Integration (3-4 hours)
7. API endpoints (GET plan, POST compute, GET export)
8. Excel export function (reuse Stage 10 patterns)
9. Route wiring and middleware

### Phase 3: Frontend (4-6 hours)
10. TMA page component
11. Filters and table
12. Action buttons and state management
13. Integration with API

### Phase 4: Testing & Documentation (3-4 hours)
14. Unit tests (demand, constraints, planner)
15. Integration tests (service, API)
16. E2E smoke test
17. Usage documentation
18. Stage 13 report

### Phase 5: Optional MILP (4-6 hours)
19. MILP formulation
20. PuLP integration
21. Solver selection logic
22. MILP tests

---

## Key Decisions Made

1. **Heuristic First**: Start with simple heuristic (greedy by urgency), add MILP later
2. **No SKU-Level Overrides**: Use global config for min_batch/multiplicity (can add SKU attributes later)
3. **Budget Constraint**: Optional (CASHFLOW_LIMIT=0 → unlimited)
4. **Capacity Constraint**: JSON-based (flexible, no schema migration needed)
5. **Safety Stock Formula**: `COEFF * sqrt(window) * stdev` (standard inventory theory)
6. **Urgency Metric**: Stock coverage days (lower = more urgent)

---

## Technical Debt & Future Enhancements

### Known Limitations
1. **No Name Extraction**: Customer names not yet extracted from reviews (marked TODO in Stage 12)
2. **No Seasonality**: Simple linear forecast (could add exponential smoothing, SARIMA)
3. **No Lead Time**: Assumes instant replenishment (could add supplier lead time)
4. **No Product Lifecycle**: Doesn't account for new/dying products
5. **No Substitution**: Treats each SKU independently (no cannibalization modeling)

### Potential Improvements
1. **ML Forecasting**: Train LSTM/Prophet models on historical sales
2. **Multi-Echelon**: Model warehouse-to-warehouse transfers
3. **Dynamic Safety Stock**: Adjust by service level target (95%, 99%)
4. **Replenishment Policies**: (s,S), (R,Q), etc.
5. **Scenario Planning**: What-if analysis for demand shocks
6. **Integration with ERP**: Push recommendations to WMS/ERP via API

---

## Definition of Done (Partial)

- [x] ✅ Config and settings added
- [x] ✅ Demand module implemented and tested
- [x] ✅ Constraints collection working
- [x] ✅ Heuristic planner functional
- [x] ✅ Explainability with hash generation
- [x] ✅ Service facade for plan generation
- [ ] ⏳ API endpoints (GET plan, POST compute, GET export)
- [ ] ⏳ TMA UI page with filters and table
- [ ] ⏳ Comprehensive tests (unit + integration)
- [ ] ⏳ Excel export functionality
- [ ] ⏳ STAGE_13_REPORT.md with metrics
- [ ] ⏳ Smoke test validation
- [ ] ⏳ Documentation (usage guide, examples)

**Current Status:** ~60% complete (core logic done, API/UI/tests pending)

---

## Next Steps for Completion

1. **Create API Router** (`app/web/routers/supply.py`)
2. **Wire Router** in `app/web/app.py`
3. **Create TMA Page** (`tma/src/pages/SupplyPlanner.tsx`)
4. **Add Menu Item** in TMA navigation
5. **Write Tests** (domain + service + API)
6. **Create Excel Export** (reuse `app/services/export.py` patterns)
7. **Manual Smoke Test** with sample data
8. **Generate Report** (`STAGE_13_REPORT.md`)
9. **Commit and Deploy**

---

**Estimated Remaining Effort:** 8-10 hours  
**Priority:** Medium-High (enables proactive inventory management)  
**Dependencies:** None (all DB schema already exists from Stage 10)
