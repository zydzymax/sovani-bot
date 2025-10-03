# Operational Runbooks — SoVAni Bot (Stage 17)

## Overview

This document provides standard operating procedures (runbooks) for common operational incidents and alerts.

## Alert Response Matrix

| Severity | Response Time | Escalation | Auto-Remediation |
|----------|--------------|-----------|------------------|
| **Critical** | < 5 minutes | Immediate to admin | Yes |
| **Error** | < 15 minutes | Within 1 hour | Yes |
| **Warning** | < 1 hour | Within 4 hours | Optional |
| **Info** | Best effort | No escalation | No |

---

## Runbook 1: API Latency SLO Breach

**Alert:** `check_api_latency_p95`
**Severity:** Warning → Error (if sustained)
**Auto-Remediation:** `remediate_clear_cache`

### Symptoms
- API p95 latency exceeds configured threshold (default: 1200ms)
- Users report slow dashboard loading
- Increased timeout errors

### Diagnosis
```bash
# Check current API metrics
curl http://localhost:8000/metrics | grep http_request_duration

# Check active database connections
sqlite3 sovani_bot.db "PRAGMA database_list; PRAGMA page_count;"

# Check system resources
top -bn1 | head -20
free -h
df -h
```

### Resolution Steps

1. **Check Database Performance**
   ```bash
   # Run EXPLAIN on slow queries
   sqlite3 sovani_bot.db
   EXPLAIN QUERY PLAN SELECT * FROM vw_inventory_snapshot LIMIT 10;
   ```

2. **Clear Application Caches**
   ```bash
   # Trigger cache clear via API (admin token required)
   curl -X POST http://localhost:8000/api/v1/ops/remediate?alert_source=check_api_latency_p95 \
     -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

3. **Check External API Dependencies**
   ```bash
   # Test WB API connectivity
   curl -H "Authorization: $WB_STATS_TOKEN" \
     https://statistics-api.wildberries.ru/api/v1/supplier/sales

   # Test Ozon API connectivity
   curl -H "Client-Id: $OZON_CLIENT_ID" \
        -H "Api-Key: $OZON_API_KEY_ADMIN" \
        https://api-seller.ozon.ru/v1/product/list
   ```

4. **Restart Service (if needed)**
   ```bash
   sudo systemctl restart sovani-bot
   sudo systemctl restart sovani-web-api
   ```

### Prevention
- Monitor database size and run VACUUM monthly
- Review and optimize slow queries
- Implement connection pooling (Stage 7+)
- Add caching for expensive operations

---

## Runbook 2: Data Ingestion Failure

**Alert:** `check_ingest_success_rate`
**Severity:** Error
**Auto-Remediation:** None (requires investigation)

### Symptoms
- No sales data ingested for yesterday
- Ingest success rate < 99% SLO
- Empty daily_sales table for recent dates

### Diagnosis
```bash
# Check last ingested date
sqlite3 sovani_bot.db "SELECT MAX(d) FROM daily_sales;"

# Check recent ingestion logs
journalctl -u sovani-scheduler -n 100 --since "1 hour ago" | grep ingest

# Test API credentials
python -c "
from app.core.config import get_settings
settings = get_settings()
print(f'WB Token: {settings.wb_stats_token[:20]}...')
print(f'Ozon Client ID: {settings.ozon_client_id}')
"
```

### Resolution Steps

1. **Verify API Credentials**
   ```bash
   # Check .env file
   grep -E '(WB_.*_TOKEN|OZON_)' .env

   # Test credentials manually
   curl -H "Authorization: $WB_STATS_TOKEN" \
     https://statistics-api.wildberries.ru/api/v1/supplier/sales?dateFrom=2025-10-01
   ```

2. **Check Rate Limits**
   ```bash
   # Check rate limit metrics
   curl http://localhost:8000/metrics | grep rate_limit

   # Review recent API call patterns
   journalctl -u sovani-scheduler --since "24 hours ago" | grep -i "rate"
   ```

3. **Manual Data Collection**
   ```bash
   # Run collection job manually
   python -c "
   from app.scheduler.jobs import collect_yesterday_data
   result = collect_yesterday_data()
   print(result)
   "
   ```

4. **Check Network Connectivity**
   ```bash
   # Test DNS resolution
   nslookup statistics-api.wildberries.ru
   nslookup api-seller.ozon.ru

   # Test connectivity
   ping -c 3 statistics-api.wildberries.ru
   ```

### Prevention
- Monitor API token expiration dates
- Set up backup tokens for critical endpoints
- Implement retry logic with exponential backoff
- Alert on consecutive ingestion failures

---

## Runbook 3: Negative Cash Balance Alert

**Alert:** `check_cash_balance_threshold`
**Severity:** Critical
**Auto-Remediation:** `remediate_notify_admin`

### Symptoms
- Cumulative cash balance below configured threshold (default: -10,000 RUB)
- High outflow rate (commissions, delivery costs)
- Delayed marketplace settlements

### Diagnosis
```bash
# Check current cash balance
sqlite3 sovani_bot.db "
SELECT d, cumulative_balance
FROM vw_cashflow_daily
ORDER BY d DESC
LIMIT 7;
"

# Check recent cashflow breakdown
sqlite3 sovani_bot.db "
SELECT d, marketplace, inflow, outflow, net
FROM cashflow_daily
WHERE d >= date('now', '-7 days')
ORDER BY d DESC;
"

# Check P&L summary
sqlite3 sovani_bot.db "
SELECT
    d,
    SUM(revenue_net) AS revenue,
    SUM(cogs) AS cogs,
    SUM(commissions) AS commissions,
    SUM(gross_profit) AS profit
FROM pnl_daily
WHERE d >= date('now', '-7 days')
GROUP BY d
ORDER BY d DESC;
"
```

### Resolution Steps

1. **Review Recent Transactions**
   ```bash
   # Identify high-outflow days
   sqlite3 sovani_bot.db "
   SELECT d, marketplace, outflow
   FROM cashflow_daily
   WHERE outflow > 5000
   ORDER BY d DESC LIMIT 10;
   "
   ```

2. **Verify Commission Calculations**
   ```bash
   # Check for commission outliers
   sqlite3 sovani_bot.db "
   SELECT * FROM vw_commission_recon
   WHERE flag_outlier = 1
   ORDER BY d DESC LIMIT 10;
   "
   ```

3. **Contact Finance Team**
   - Notify manager via Telegram (auto-triggered)
   - Request expedited settlement from marketplaces
   - Review payment terms and schedules

4. **Adjust Business Operations**
   - Pause new orders if cash reserves critical
   - Accelerate receivables collection
   - Defer non-essential payments

### Prevention
- Monitor cash balance daily
- Maintain emergency cash reserves (30+ days)
- Negotiate better payment terms with marketplaces
- Implement cashflow forecasting (Stage 16+)

---

## Runbook 4: Commission Reconciliation Outliers

**Alert:** `check_commission_outliers`
**Severity:** Warning
**Auto-Remediation:** None (requires manual review)

### Symptoms
- Multiple commission calculation variances >5%
- Unexpected commission charges
- Discrepancies between actual and calculated commissions

### Diagnosis
```bash
# List all outliers
sqlite3 sovani_bot.db "
SELECT
    d,
    sku_id,
    marketplace,
    actual_commission,
    calc_commission,
    delta_abs,
    delta_pct
FROM vw_commission_recon
WHERE flag_outlier = 1
    AND d >= date('now', '-7 days')
ORDER BY ABS(delta_pct) DESC
LIMIT 20;
"

# Check commission rules
sqlite3 sovani_bot.db "
SELECT * FROM commission_rules
WHERE marketplace = 'WB' OR marketplace = 'OZON';
"
```

### Resolution Steps

1. **Identify Root Cause**
   - **Category Changes**: SKU moved to different commission category
   - **Rate Updates**: Marketplace updated commission rates
   - **Special Fees**: Penalties, fines, or one-time charges
   - **Data Quality**: Missing or incorrect rate_pct in commission_rules

2. **Update Commission Rules**
   ```sql
   -- Update commission rate for category
   UPDATE commission_rules
   SET rate_pct = 12.5, updated_at = CURRENT_TIMESTAMP
   WHERE marketplace = 'OZON'
     AND category = 'Electronics';
   ```

3. **Recalculate Affected Periods**
   ```bash
   # Trigger reconciliation recompute
   curl -X POST "http://localhost:8000/api/v1/finance/reconcile?date_from=2025-09-01&date_to=2025-09-30" \
     -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

4. **Document Findings**
   - Log explanation in ops_alerts_history
   - Update commission rules documentation
   - Notify finance team of changes

### Prevention
- Monitor marketplace announcements for rate changes
- Automate commission rule updates via API (if available)
- Set up monthly reconciliation reviews
- Maintain historical commission rate log

---

## Runbook 5: Database Growth Alert

**Alert:** `check_db_growth`
**Severity:** Warning → Error (if approaching limits)
**Auto-Remediation:** `remediate_vacuum_db`

### Symptoms
- Database size exceeds threshold (default: 5GB)
- Slow query performance
- Disk space warnings

### Diagnosis
```bash
# Check database size
sqlite3 sovani_bot.db "
PRAGMA page_count;
PRAGMA page_size;
"

# Check largest tables
sqlite3 sovani_bot.db "
SELECT name FROM sqlite_master WHERE type='table';
"

# Analyze table sizes (requires shell access)
du -sh sovani_bot.db*

# Check disk space
df -h /
```

### Resolution Steps

1. **Run VACUUM**
   ```bash
   # Manual VACUUM (requires downtime)
   sqlite3 sovani_bot.db "VACUUM;"

   # Or trigger via API
   curl -X POST http://localhost:8000/api/v1/ops/remediate?alert_source=check_db_growth \
     -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

2. **Archive Old Data**
   ```bash
   # Export data older than 180 days
   sqlite3 sovani_bot.db <<EOF
   .mode csv
   .output archive_sales_2025.csv
   SELECT * FROM daily_sales WHERE d < date('now', '-180 days');
   EOF

   # Delete archived data
   sqlite3 sovani_bot.db "
   DELETE FROM daily_sales WHERE d < date('now', '-180 days');
   VACUUM;
   "
   ```

3. **Optimize Indexes**
   ```sql
   -- Rebuild indexes
   REINDEX;

   -- Analyze for query planner
   ANALYZE;
   ```

4. **Consider Migration to PostgreSQL**
   - SQLite limit: ~140GB theoretical, ~10GB practical
   - PostgreSQL recommended for production (Stage 7+)

### Prevention
- Schedule monthly VACUUM operations
- Implement data retention policies
- Monitor database growth trends
- Plan migration to PostgreSQL for larger datasets

---

## Runbook 6: Scheduler Job Failures

**Alert:** `check_scheduler_on_time`
**Severity:** Warning → Error (consecutive failures)
**Auto-Remediation:** `remediate_restart_scheduler`

### Symptoms
- Scheduler jobs not executing on time
- Missing data for expected dates
- Scheduler on-time rate < 98% SLO

### Diagnosis
```bash
# Check scheduler service status
sudo systemctl status sovani-scheduler

# Check recent job execution logs
journalctl -u sovani-scheduler -n 50 --since "1 hour ago"

# Check for job errors
journalctl -u sovani-scheduler --since "24 hours ago" | grep -i error

# Check system resources during job execution
top -bn1 | head -20
```

### Resolution Steps

1. **Restart Scheduler Service**
   ```bash
   sudo systemctl restart sovani-scheduler
   sudo systemctl status sovani-scheduler
   ```

2. **Check Job Configuration**
   ```bash
   # Review scheduler config
   cat /etc/systemd/system/sovani-scheduler.service

   # Check cron jobs (if using cron)
   crontab -l
   ```

3. **Run Jobs Manually**
   ```bash
   # Test collect_yesterday_data
   python -c "
   from app.scheduler.jobs import collect_yesterday_data
   result = collect_yesterday_data()
   print(result)
   "

   # Test recalc_recent_metrics
   python -c "
   from app.scheduler.jobs import recalc_recent_metrics
   result = recalc_recent_metrics(days=7)
   print(result)
   "
   ```

4. **Review Error Logs**
   ```bash
   # Check for Python errors
   journalctl -u sovani-scheduler --since "1 hour ago" | grep Traceback -A 10
   ```

### Prevention
- Monitor scheduler job execution metrics
- Set up job heartbeat checks
- Implement job timeout handling
- Add redundancy for critical jobs

---

## Emergency Contacts

- **System Admin**: Telegram @username (manager_chat_id in config)
- **Finance Team**: finance@company.com
- **DevOps Oncall**: oncall@company.com
- **Marketplace Support**:
  - WB: support@wildberries.ru
  - Ozon: seller@ozon.ru

---

## Useful Commands

### Database Inspection
```bash
# Connect to database
sqlite3 sovani_bot.db

# List all tables
.tables

# Show table schema
.schema daily_sales

# Export query results
.mode csv
.output results.csv
SELECT * FROM vw_inventory_snapshot LIMIT 100;
.quit
```

### Service Management
```bash
# Check all SoVAni services
sudo systemctl status sovani-bot
sudo systemctl status sovani-web-api
sudo systemctl status sovani-scheduler

# View logs
journalctl -u sovani-bot -f
journalctl -u sovani-web-api -f
journalctl -u sovani-scheduler -f

# Restart services
sudo systemctl restart sovani-bot
sudo systemctl restart sovani-web-api
sudo systemctl restart sovani-scheduler
```

### API Testing
```bash
# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics

# Run health checks manually
curl -X POST http://localhost:8000/api/v1/ops/run-detectors \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Check SLO compliance
curl http://localhost:8000/api/v1/ops/slo/summary?days=7
```

---

## Version History

- **v1.0** (2025-10-02): Initial runbooks for Stage 17
- Future: Add runbooks for Stages 18-20 (Reviews SLA, Multi-tenant, Launch)
