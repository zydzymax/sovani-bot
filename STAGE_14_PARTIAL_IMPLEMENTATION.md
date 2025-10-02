# Stage 14 — Pricing & Promo Analytics: Partial Implementation

**Status:** 🟡 Foundational Components + Implementation Plan  
**Complexity:** Very High (Advanced Analytics + Guardrails)  
**Estimated Full Effort:** 20-24 hours

---

## Executive Summary

Stage 14 реализует аналитику цен и промо-акций с оценкой эластичности спроса, измерением эффектов промо и генерацией рекомендаций по ценообразованию с учётом guardrails (минимальная маржа, MAP, максимальная скидка).

**Ключевая особенность:** Используются только реальные данные из БД (176 дней истории из-за ограничений WB API), без выдуманных параметров.

---

## ✅ Completed Components

### 1. Configuration (`.env.example` + `app/core/config.py`) ✅

Добавлены настройки:
```bash
PRICING_MIN_MARGIN_PCT=0.10         # Минимальная маржа 10%
PRICING_MAX_DISCOUNT_PCT=0.30       # Максимальная скидка 30%
PRICING_MIN_PRICE_STEP=10           # Минимальный шаг цены (руб)
PRICING_MAP_JSON={}                 # MAP (минимальная цена) по SKU
PROMO_MIN_WINDOW_DAYS=7             # Минимальное окно сравнения
PROMO_MAX_WINDOW_DAYS=28            # Максимальное окно
PRICING_EXPLAIN_SERVICE_LEVEL=0.88  # Service level для пояснений
```

### 2. Elasticity Module (`app/domain/pricing/elasticity.py`) ✅

**Реализовано:**
- `build_price_demand_series()` — построение временного ряда цена-спрос
  - Источник: `DailySales` (qty, revenue_gross) + `DailyStock` (on_hand)
  - Proxy цены: `revenue_gross / qty`
  - Фильтрация stockouts, выбросов
  - Окно: 176 дней (лимит WB API)

- `estimate_price_elasticity()` — оценка эластичности
  - Метод: log-log OLS (ln(units) ~ ln(price))
  - Простая ковариация без statsmodels
  - Quality assessment: "low" | "medium"
  - Минимум 21 наблюдение для "medium" quality

**Алгоритм:**
```python
elasticity = cov(ln_price, ln_units) / var(ln_price)

Quality:
- "low" if observations < 21
- "low" if price variance < 0.01
- "low" if elasticity > 0 (аномалия)
- "medium" otherwise
```

---

## 🔴 Missing Components (TODO)

### 3. Promo Effects Module (`app/domain/pricing/promo_effects.py`)

**Функции:**

```python
def measure_promo_lift(series: list[PriceDemandPoint], window: int = 14) -> dict:
    """
    Сравнение до/после промо:
    1. Выделить промо-периоды (promo_flag=True)
    2. Сопоставить с baseline (те же дни недели без промо)
    3. Рассчитать lift = (units_promo - units_baseline) / units_baseline
    
    Returns:
        {
            "lift": float,  # Относительный рост (например, 0.18 = +18%)
            "ci_low": float | None,
            "ci_high": float | None,
            "quality": "low" | "medium"
        }
    """
```

**Правила:**
- Сопоставление по weekday (пятница с пятницей)
- Минимум 7 наблюдений для quality="medium"
- Фильтрация выбросов (lift > 5x или < -0.9)

### 4. Price Recommendation Module (`app/domain/pricing/recommend.py`)

**Функции:**

```python
def simulate_price_change(units: float, elasticity: float, price: float, delta: float) -> dict:
    """
    Прогноз спроса при изменении цены:
    units_new = units * (price / (price + delta)) ** elasticity
    
    Returns:
        {
            "new_price": float,
            "expected_units": float,
            "expected_revenue": float,
            "expected_profit": float  # С учётом cost, commissions, delivery
        }
    """

def recommend_price_or_discount(
    *,
    sku_info: dict,  # {sku_id, current_price, unit_cost, commission_rate, avg_delivery}
    series: list[PriceDemandPoint],
    el: ElasticityEstimate,
    promo: dict,
    settings: Settings,
) -> dict:
    """
    Генерация рекомендации с guardrails:
    
    Guardrails:
    1. min_margin: (price - cost - comm - delivery) / price >= PRICING_MIN_MARGIN_PCT
    2. MAP: price >= PRICING_MAP_JSON.get(sku, 0)
    3. step: abs(delta) >= PRICING_MIN_PRICE_STEP or delta=0
    4. max_discount: -delta / price <= PRICING_MAX_DISCOUNT_PCT
    
    Returns:
        {
            "sku_id": int,
            "suggested_price": float | None,
            "suggested_discount_pct": float | None,
            "expected_units": float,
            "expected_profit": float,
            "guardrails": {
                "min_margin_ok": bool,
                "map_ok": bool,
                "step_ok": bool,
                "max_discount_ok": bool
            },
            "reason_code": str  # "increase_margin" | "promo_lift" | "keep" | "low_quality"
        }
    """
```

**Логика рекомендаций:**
- Если quality="low" → reason_code="low_quality", suggested_price=None
- Если эластичность умеренная (|e| < 1.5) → небольшие корректировки
- Если эластичность высокая (|e| > 2) → осторожные изменения
- Если promo lift > 15% → рассмотреть периодические промо
- Всегда проверять все guardrails перед рекомендацией

### 5. Explainability Module (`app/domain/pricing/explain.py`)

```python
def build_pricing_explanation(
    sku: str,
    current_price: float,
    suggested_price: float | None,
    elasticity: float | None,
    lift: float | None,
    guardrails: dict,
    expected_profit_change: float,
    action: str,
) -> tuple[str, str]:
    """
    Генерация объяснения + SHA256 хэш.
    
    Пример:
    "SKU123: текущ. цена 1490₽, эластичность≈-1.2 (сред), lift промо≈+18%, 
     min_margin=10% ✓, MAP=1290₽ ✓ → рекомендовано -20₽ (шаг 10₽); 
     ожид. прибыль +3.5%"
    
    Returns:
        (explanation_text, rationale_hash)
    """
```

### 6. Pricing Service (`app/services/pricing_service.py`)

```python
def compute_pricing_for_skus(
    db: Session,
    sku_ids: list[int] | None = None,
    marketplace: str | None = None,
    window: int = 28,
) -> list[dict]:
    """
    Orchestration:
    1. Fetch SKU info (current price, cost, commissions)
    2. Build price-demand series
    3. Estimate elasticity
    4. Measure promo effects
    5. Generate recommendations
    6. Save to PricingAdvice table
    7. Return results with explanations
    """
```

### 7. Database Model & Migration

**Table: `pricing_advice`**
```sql
CREATE TABLE pricing_advice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    d DATE NOT NULL,                    -- Date of advice
    sku_id INTEGER NOT NULL,
    marketplace VARCHAR(10),
    suggested_price FLOAT,              -- Recommended price
    suggested_discount_pct FLOAT,       -- Recommended discount %
    expected_profit FLOAT,              -- Expected profit change
    quality VARCHAR(10),                -- "low" | "medium"
    reason_code VARCHAR(50),            -- Action rationale
    rationale_hash VARCHAR(64),         -- SHA256 of explanation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(d, sku_id)
);

CREATE INDEX idx_pricing_advice_sku ON pricing_advice(sku_id);
CREATE INDEX idx_pricing_advice_quality ON pricing_advice(quality);
```

**Migration:**
```bash
alembic revision --autogenerate -m "Add pricing_advice table"
alembic upgrade head
```

### 8. API Endpoints (`app/web/routers/pricing.py`)

```python
@router.get("/api/v1/pricing/advice")
async def get_pricing_advice(
    db: Session,
    marketplace: str | None = None,
    sku_id: int | None = None,
    quality: str | None = None,  # Filter by quality
    limit: int = 50,
    offset: int = 0,
):
    """Get pricing recommendations."""

@router.post("/api/v1/pricing/compute")
async def compute_pricing(
    db: Session,
    _admin: Annotated[dict, Depends(require_admin)],
    marketplace: str | None = None,
    sku_id: int | None = None,
    window: int = 28,
):
    """Recompute pricing recommendations (admin-only)."""

@router.get("/api/v1/export/pricing_advice.csv")
async def export_pricing_csv(db: Session):
    """Export pricing advice to CSV."""

@router.get("/api/v1/export/pricing_advice.xlsx")
async def export_pricing_xlsx(db: Session):
    """Export pricing advice to Excel."""
```

### 9. Tests

**Required Test Files:**
```
tests/domain/test_elasticity.py         (10 tests)
tests/domain/test_promo_effects.py      (6 tests)
tests/domain/test_recommend.py          (8 tests)
tests/services/test_pricing_service.py  (5 tests)
tests/web/test_pricing_api.py           (6 tests)
```

**Test Scenarios:**

**`test_elasticity.py`:**
- `test_build_series_filters_stockouts()`
- `test_build_series_filters_outliers()`
- `test_estimate_insufficient_data_returns_low()`
- `test_estimate_low_variance_returns_low()`
- `test_estimate_positive_elasticity_returns_low()`
- `test_estimate_normal_elasticity_returns_medium()`

**`test_promo_effects.py`:**
- `test_measure_lift_weekday_matching()`
- `test_measure_lift_insufficient_data()`
- `test_measure_lift_filters_outliers()`

**`test_recommend.py`:**
- `test_simulate_price_increase_reduces_demand()`
- `test_recommend_respects_min_margin()`
- `test_recommend_respects_map()`
- `test_recommend_respects_min_step()`
- `test_recommend_respects_max_discount()`
- `test_recommend_low_quality_no_suggestion()`

---

## Current Implementation Status

### ✅ Completed (30%):
1. Configuration (ENV + Settings)
2. Elasticity module (build_series + estimate)
3. Domain structure

### ⏳ Remaining (70%):
1. Promo effects measurement
2. Price recommendation with guardrails
3. Explainability (text + hash)
4. Pricing service
5. Database migration
6. API endpoints
7. Comprehensive tests
8. TMA UI (optional)

---

## Technical Challenges

### 1. Data Quality Issues
- **WB API Limit:** Only 176 days history
- **Price Proxy:** Using revenue/units (not perfect)
- **Stockout Detection:** Heuristic (on_hand < 5)
- **Promo Detection:** No explicit flag in current schema

**Solutions:**
- Store explicit promo flags in `DailySales.promo_cost`
- Add price history table for accurate prices
- Improve stockout detection with velocity

### 2. Statistical Rigor
- **Simple OLS:** No confidence intervals
- **No Seasonality Adjustment:** Only weekday controls
- **No Autocorrelation Handling:** Simplistic estimation

**Solutions (Future):**
- Integrate `statsmodels` for proper regression
- Add seasonality decomposition
- Use ARIMA/Prophet for forecasting

### 3. Guardrails Complexity
- **Multiple Constraints:** min_margin, MAP, step, max_discount
- **Conflicting Goals:** Maximize profit vs respect MAP
- **Dynamic Costs:** Commissions/delivery vary by date

**Solutions:**
- Hierarchical constraint checking
- Multi-objective optimization (Pareto frontier)
- Rolling average costs for stability

---

## Implementation Priority

### Phase 1: Core Analytics (8-10 hours)
1. ✅ Configuration
2. ✅ Elasticity estimation
3. Promo effects measurement
4. Price simulation

### Phase 2: Recommendations (6-8 hours)
5. Recommendation logic with guardrails
6. Explainability module
7. Database migration

### Phase 3: Service & API (4-6 hours)
8. Pricing service orchestration
9. API endpoints
10. Export functions

### Phase 4: Testing (6-8 hours)
11. Unit tests (elasticity, promo, recommend)
12. Integration tests (service)
13. API tests
14. E2E smoke tests

---

## Usage Examples (When Completed)

### API: Get Recommendations
```bash
curl "http://localhost:8000/api/v1/pricing/advice?marketplace=WB&quality=medium"
```

### API: Recompute (Admin)
```bash
curl -X POST "http://localhost:8000/api/v1/pricing/compute?marketplace=WB&window=28" \
  -H "Authorization: Bearer <admin_token>"
```

### Programmatic:
```python
from app.services.pricing_service import compute_pricing_for_skus

advice = compute_pricing_for_skus(db, marketplace="WB", window=28)
for rec in advice:
    print(f"{rec['article']}: {rec['suggested_price']}₽ (elasticity: {rec['elasticity']})")
```

---

## Next Steps for Completion

1. **Implement Promo Module** (`promo_effects.py`)
2. **Implement Recommendation Module** (`recommend.py`)
3. **Implement Explainability** (`explain.py`)
4. **Create Pricing Service** (`pricing_service.py`)
5. **Database Migration** (PricingAdvice table)
6. **API Endpoints** (`pricing.py`)
7. **Write Tests** (35+ test cases)
8. **Manual Smoke Test** with real data
9. **Generate Full Report** (`STAGE_14_REPORT.md`)
10. **Commit & Deploy**

**Estimated Remaining Effort:** 16-20 hours

---

**Current Status:** 🟡 Foundational components in place, core analytics partially implemented  
**Recommendation:** Complete promo + recommendation modules before deploying to production
