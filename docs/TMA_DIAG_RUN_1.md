# TMA Diagnostic Run #1 - Initial State

**Date**: 2025-10-05
**Environment**: Production (app.justbusiness.lol)

## Summary of Issues

1. **403 Forbidden** - Authentication/authorization failures
2. **500 Internal Server Error** - Missing database tables/columns
3. **All zeros in dashboards** - No data in key tables

---

## Issue #1: 403 Forbidden

### Reproduction
```bash
curl -s 'https://app.justbusiness.lol/api/v1/dashboard/summary?date_from=2025-09-01&date_to=2025-10-05' \
  -H 'X-Telegram-Init-Data: fake_init_data'
```

### Response
```json
{
  "detail": "Invalid Telegram initData"
}
```

### Root Cause
- No detailed reason code in 403 response
- Cannot distinguish between:
  - Invalid HMAC signature
  - User not in organization
  - Insufficient role permissions
  - Missing X-Telegram-Init-Data header

### Server Logs
- No request_id in error responses
- Limited diagnostic information

---

## Issue #2: 500 Internal Server Error

### Previous Errors (from user reports)
- `AttributeError: 'Settings' object has no attribute 'timezone'` → **FIXED**
- `sqlite3.OperationalError: no such table: users` → **FIXED**
- `OperationalError: no such column: Review.org_id` → **FIXED**

### Current State
- Web server running without crashes
- No 500 errors in recent logs

---

## Issue #3: All Zeros in Dashboards

### Data Presence Analysis
```sql
-- Results from sovani_bot.db

reviews:        org_id=1: 55 rows ✓
daily_sales:    NO DATA ✗
daily_stock:    NO DATA ✗
metrics_daily:  NO DATA ✗
pnl_daily:      NO DATA ✗
```

### Root Causes
1. **No sales/stock data collected** - ingestion not running
2. **Data collection script started but not completed** (collect_recent_data.py running)
3. **Date window mismatch** - Dashboard requests last 30 days, but no data in that range

### User Experience
- Dashboard: Revenue 0₽, Profit 0₽, Margin 0%, Units 0
- Finance: Same zeros
- Reviews: Should show 55 reviews (if endpoint works)
- Inventory: "Данных нет" (correct, table is empty)

---

## Configuration State

### Database
- File: `/root/sovani_bot/sovani_bot.db`
- Alembic version: `7f1a26783f04` (head)
- Organizations: 1 (id=1, "SoVAni Default")
- Users: 1 (tg_user_id=769582971)

### Authentication
- BOT_TOKEN: 8320329020:AAF-JeUX08V2eQHsnT8pX51_lB1-zFQENO8
- ALLOWED_TG_USER_IDS: 769582971
- Auth method: Old `current_user()` in deps.py (not multi-tenant `get_current_user()`)

### Web Server
- Running: uvicorn app.web.main:app on port 8000
- Domain: https://app.justbusiness.lol
- Nginx: SSL configured, reverse proxy active

---

## Next Steps

1. **Fix 403**: Add reason codes, improve error messages
2. **Add DEV mode**: /api/v1/dev/impersonate for testing
3. **Implement auto-join**: New users → Default org as viewer
4. **Add self-check endpoint**: /api/v1/ops/self-check
5. **Wait for data collection**: collect_recent_data.py to complete
6. **Add diagnostic page**: TMA diagnostics UI
