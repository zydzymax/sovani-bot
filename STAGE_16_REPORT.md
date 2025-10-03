# Stage 16 — Cashflow & PnL Pro

**Status:** ✅ Complete
**Date:** 2025-10-02

## Summary

Stage 16 implements comprehensive cash flow and P&L analysis with daily reconciliation, actual cost tracking, and what-if scenario modeling. The system provides a complete financial picture using real marketplace data with proper cost allocation strategies.

### Key Features

1. **Daily Cashflow**: Inflow/outflow tracking with settlement lag approximation
2. **Actual P&L**: Revenue, COGS, gross profit with flexible cost strategies
3. **Commission Reconciliation**: Automatic variance detection (>5% flagged)
4. **Scenario Analysis**: Pricing and supply what-if simulations
5. **API & Exports**: REST endpoints with CSV exports for BI integration

## Implementation

### Database Schema

**Tables Created:**
- `cashflow_daily` (d, marketplace, inflow, outflow, net, src_hash) - PK: (d, marketplace)
- `pnl_daily` (d, sku_id, marketplace, revenue_net, cogs, gross_profit, refunds, delivery_cost, promo_cost, commissions, writeoffs, margin_pct, src_hash) - PK: (d, sku_id, marketplace)

**Views Created:**
- `vw_cashflow_daily` - With cumulative balance
- `vw_pnl_actual_daily` - With article info
- `vw_commission_recon` - Variance analysis with outlier flagging

### Configuration

```bash
CF_DEFAULT_SETTLEMENT_LAG_DAYS=7              # Payment lag MP → seller
CF_NEGATIVE_BALANCE_ALERT_THRESHOLD=-10000    # Alert threshold
PNL_COST_FALLBACK_STRATEGY=latest             # latest | moving_avg_28
PNL_REFUNDS_RECOGNITION=post_event            # post_event | order_date
SCENARIO_MAX_LOOKAHEAD_DAYS=28                # Max scenario horizon
SCENARIO_PRICE_STEP=10                        # Price step (rubles)
SCENARIO_SUPPLY_LEADTIME_DAYS=5               # Supply leadtime
```

### Domain Logic

#### 1. Cashflow (`app/domain/finance/cashflow.py`)

**Function:** `build_daily_cashflow(db, d_from, d_to)`

- Aggregates sales data by date and marketplace
- Calculates inflow (revenue - refunds) with settlement lag
- Calculates outflow (commissions + delivery + promo)
- Returns net cashflow with idempotency hash
- **Note**: Uses approximation with lag when actual payment data unavailable

**Example Output:**
```python
{
    "d": date(2025, 10, 09),  # Settlement date (sale + 7 days)
    "marketplace": "WB",
    "inflow": 15000.00,
    "outflow": 2250.00,
    "net": 12750.00,
    "src_hash": "abc123...",
    "reason_code": "approximation_with_lag"
}
```

#### 2. Actual P&L (`app/domain/finance/pnl_actual.py`)

**Function:** `compute_daily_pnl(db, d_from, d_to, cost_strategy)`

- Retrieves sales data with marketplace join
- Gets unit cost using strategy:
  - `latest`: Most recent cost before/on date
  - `moving_avg_28`: 28-day moving average
- Calculates COGS, gross profit, margin %
- Idempotent upsert with hash validation

**Cost Strategies:**

**Latest:**
```sql
SELECT cost_price FROM cost_price_history
WHERE sku_id = ? AND dt_from <= ?
ORDER BY dt_from DESC LIMIT 1
```

**Moving Average 28:**
```sql
SELECT AVG(cost_price) FROM cost_price_history
WHERE sku_id = ? AND dt_from BETWEEN (date - 28) AND date
```

#### 3. Commission Reconciliation (`app/domain/finance/recon.py`)

**View:** `vw_commission_recon`

Compares:
- **Actual**: From `daily_sales.commission_amount`
- **Calculated**: `(revenue_gross * rate_pct / 100) + (fixed_per_unit * qty)`

**Outlier Detection:**
```sql
CASE WHEN ABS(delta_pct) > 5.0 THEN 1 ELSE 0 END AS flag_outlier
```

**Example Outlier:**
```
d: 2025-09-15
sku_id: 123
actual_commission: 150.00
calc_commission: 120.00
delta_abs: 30.00
delta_pct: 20.0%  ← FLAGGED
```

#### 4. Scenario Analysis (`app/domain/finance/scenario.py`)

**Pricing Scenario:**
- Uses elasticity from Stage 14
- Simulates demand at new price
- Calculates profit impact

**Supply Scenario:**
- Uses velocity (sv14) from metrics
- Calculates coverage days from added stock

**Combined:**
- Runs both scenarios
- Returns integrated quality assessment

### API Endpoints

#### Compute Endpoints (Admin Only)

**POST** `/api/v1/finance/cashflow/compute`
```bash
curl -X POST "http://localhost:8000/api/v1/finance/cashflow/compute?\
date_from=2025-09-01&date_to=2025-09-30" \
  -H "Authorization: Bearer <admin_token>"
```

**Response:**
```json
{
  "status": "success",
  "records_processed": 30,
  "records_upserted": 28
}
```

**POST** `/api/v1/finance/pnl/compute`
```bash
curl -X POST "http://localhost:8000/api/v1/finance/pnl/compute?\
date_from=2025-09-01&date_to=2025-09-30&cost_strategy=latest"
```

**POST** `/api/v1/finance/reconcile`
```bash
curl -X POST "http://localhost:8000/api/v1/finance/reconcile?\
date_from=2025-09-01&date_to=2025-09-30"
```

**Response:**
```json
{
  "status": "success",
  "outliers_found": 5,
  "outliers": [...]
}
```

#### Scenario Endpoint

**POST** `/api/v1/finance/scenario`
```json
{
  "sku_id": 123,
  "new_price": 950.0,
  "add_qty": 100,
  "horizon_days": 28,
  "leadtime_days": 5
}
```

**Response:**
```json
{
  "pricing": {
    "current_price": 1000.0,
    "new_price": 950.0,
    "projected_units": 105.3,
    "profit_change": -525.00,
    "quality": "medium"
  },
  "supply": {
    "add_qty": 100,
    "current_velocity": 5.2,
    "added_coverage_days": 19.2,
    "quality": "medium"
  },
  "combined_quality": "medium"
}
```

#### Export Endpoints

**GET** `/api/v1/finance/export/cashflow.csv`
**GET** `/api/v1/finance/export/pnl.csv`

## Data Flow

### Cashflow Calculation Flow

```
DailySales → Aggregate by (d, marketplace) → Apply settlement lag
→ Calculate inflow/outflow → Generate hash → Upsert to cashflow_daily
```

### P&L Calculation Flow

```
DailySales → Join SKU → Get unit_cost (strategy) → Calculate COGS
→ Compute gross_profit & margin → Generate hash → Upsert to pnl_daily
```

### Reconciliation Flow

```
DailySales → Join CommissionRules → Calculate expected commission
→ Compare with actual → Flag outliers (>5%) → Return variances
```

## Key Design Decisions

### 1. Settlement Lag Approximation

**Rationale**: Marketplace APIs don't provide real-time payment data

**Implementation**:
- Use configurable lag (default 7 days)
- Mark records with `reason_code: "approximation_with_lag"`
- Can be replaced with actual payment data when available

### 2. Cost Strategies

**Latest**: Fast, reflects current costs
- ✅ Simple, no computation
- ❌ May not reflect historical reality

**Moving Average 28**: Smoothed, more representative
- ✅ Accounts for cost fluctuations
- ❌ More complex queries

### 3. Idempotent Upserts

**Hash Formula**: `f"{d}|{sku_id}|{marketplace}|{revenue_net:.2f}|{cogs:.2f}"`

**Behavior**:
- Compare `src_hash` on upsert
- Update only if hash differs
- Prevents duplicate processing

### 4. Scenario Quality Indicators

**Medium**: Elasticity available, velocity > 0
**Low**: Missing data or quality indicators from Stage 13/14

## Data Limitations

### WB API Constraint

- **Max History**: 176 days
- **Solution**: Use accumulated database records for historical analysis

### Cost Price Data

- **Fallback**: If no cost price found, defaults to 0.0
- **Recommendation**: Maintain cost_price_history regularly

### Commission Rules

- **Missing Rules**: Falls back to actual commission (delta = 0)
- **Recommendation**: Keep commission_rules up to date

## Files Created/Modified

**Created:**
- `migrations/versions/f54e77fed756_stage16_cashflow_and_pnl_schema.py` (151 lines)
- `app/domain/finance/__init__.py`
- `app/domain/finance/cashflow.py` (148 lines)
- `app/domain/finance/pnl_actual.py` (135 lines)
- `app/domain/finance/recon.py` (18 lines)
- `app/domain/finance/scenario.py` (76 lines)
- `app/services/cashflow_pnl.py` (36 lines)
- `app/web/routers/finance.py` (70 lines)
- `STAGE_16_REPORT.md` (this file)

**Modified:**
- `.env.example` (+7 finance settings)
- `app/core/config.py` (+7 finance fields)
- `app/web/main.py` (integrated finance router)

**Total**: 9 files created, 3 modified (~650 lines added)

## Example Usage

### 1. Compute Cashflow for September

```bash
curl -X POST "http://localhost:8000/api/v1/finance/cashflow/compute?\
date_from=2025-09-01&date_to=2025-09-30" \
  -H "Authorization: Bearer <token>"
```

### 2. Compute P&L with Moving Average Costs

```bash
curl -X POST "http://localhost:8000/api/v1/finance/pnl/compute?\
date_from=2025-09-01&date_to=2025-09-30&cost_strategy=moving_avg_28"
```

### 3. Run Reconciliation

```bash
curl -X POST "http://localhost:8000/api/v1/finance/reconcile?\
date_from=2025-09-01&date_to=2025-09-30"
```

### 4. Test Pricing Scenario

```bash
curl -X POST "http://localhost:8000/api/v1/finance/scenario" \
  -H "Content-Type: application/json" \
  -d '{
    "sku_id": 123,
    "new_price": 950.0,
    "horizon_days": 28
  }'
```

### 5. Export Cashflow

```bash
curl "http://localhost:8000/api/v1/finance/export/cashflow.csv?\
date_from=2025-09-01&date_to=2025-09-30" -o cashflow_sept.csv
```

## Performance Characteristics

- **Cashflow Computation**: O(n) where n = unique (d, marketplace) pairs
- **P&L Computation**: O(n × m) where n = sales records, m = cost lookups
- **Reconciliation**: O(n) with view-based calculation
- **Scenarios**: O(1) for single SKU analysis

## Future Enhancements

1. **Real Payment Data**: Replace approximation with actual marketplace payments
2. **Writeoffs Tracking**: Add product losses, damages, penalties
3. **Multi-currency**: Support international sales
4. **Automated Alerts**: Prometheus integration for negative balance
5. **Advanced Scenarios**: Multi-SKU portfolio optimization

## Verification

```bash
# Check tables created
python -c "
from sqlalchemy import create_engine, inspect
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)
inspector = inspect(engine)

tables = ['cashflow_daily', 'pnl_daily']
for table in tables:
    if table in inspector.get_table_names():
        print(f'✓ {table} created')
    else:
        print(f'✗ {table} missing')

views = ['vw_cashflow_daily', 'vw_pnl_actual_daily', 'vw_commission_recon']
for view in views:
    if view in inspector.get_view_names():
        print(f'✓ {view} created')
    else:
        print(f'✗ {view} missing')
"

# Verify imports
python -c "
from app.web.routers import finance
from app.services import cashflow_pnl
from app.domain.finance import cashflow, pnl_actual, recon, scenario
print('✓ All finance modules imported successfully')
"
```

## Conclusion

Stage 16 delivers a complete financial analysis system:

✅ **Daily Cashflow** - Inflow/outflow with settlement lag
✅ **Actual P&L** - Flexible cost strategies (latest/moving avg)
✅ **Commission Reconciliation** - Automatic variance detection
✅ **Scenario Analysis** - Pricing & supply what-if modeling
✅ **API & Exports** - REST endpoints with CSV integration
✅ **Production Ready** - Idempotent, hash-validated, configurable

The system provides financial visibility using real data from marketplace APIs, respecting the 176-day WB limit while leveraging accumulated historical data for analysis.
