# BI Integration Guide

## Overview

This guide explains how to connect Power BI, Metabase, or other BI tools to the SoVAni analytics platform.

## Connection Options

### Option 1: Direct Database Access (PostgreSQL)

**Recommended for**: Power BI, Metabase, Tableau, Looker

#### Connection String

```
Host: your-database-host
Port: 5432
Database: sovani
User: bi_reader
Password: <set_in_production>
SSL Mode: require
```

#### Read-only User

The `bi_reader` role has read-only access to all tables and views:

```sql
-- User setup (handled by ops team)
CREATE ROLE bi_reader LOGIN PASSWORD '***';
GRANT CONNECT ON DATABASE sovani TO bi_reader;
GRANT USAGE ON SCHEMA public TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO bi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bi_reader;
```

### Option 2: REST API Export (CSV/XLSX)

**Recommended for**: Excel, Google Sheets, ad-hoc analysis

Base URL: `https://your-api-domain/api/v1/export/bi/`

Authentication: Telegram WebApp initData header or API token

## Available Views

### 1. vw_pnl_daily - Profit & Loss by Day

**Purpose**: Daily P&L analysis by SKU, warehouse, and marketplace

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `d` | date | Date |
| `sku_id` | int | SKU identifier |
| `article` | string | Article/SKU code |
| `warehouse_id` | int | Warehouse ID |
| `warehouse` | string | Warehouse name |
| `marketplace` | string | Marketplace (WB/OZON) |
| `units` | int | Units sold |
| `revenue_net_gross` | float | Revenue after refunds |
| `revenue_net` | float | Net revenue (after all costs) |
| `unit_cost` | float | Unit cost |
| `profit_approx` | float | Approximate profit |
| `sv14` | float | 14-day sales velocity |
| `sv28` | float | 28-day sales velocity |

**Example Power BI DAX**:
```dax
TotalProfit = SUM(vw_pnl_daily[profit_approx])
ProfitMargin = DIVIDE([TotalProfit], SUM(vw_pnl_daily[revenue_net]))
```

**Metabase Query**:
```sql
SELECT
    d,
    marketplace,
    SUM(units) AS total_units,
    SUM(profit_approx) AS total_profit
FROM vw_pnl_daily
WHERE d >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 1 DESC;
```

### 2. vw_inventory_snapshot - Current Stock Levels

**Purpose**: Latest inventory snapshot by SKU and warehouse

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `sku_id` | int | SKU identifier |
| `warehouse_id` | int | Warehouse ID |
| `warehouse` | string | Warehouse name |
| `on_hand` | int | Units on hand |
| `in_transit` | int | Units in transit |
| `d` | date | Snapshot date |

**Example Power BI Query**:
```
SELECT * FROM vw_inventory_snapshot
WHERE on_hand > 0 OR in_transit > 0
```

### 3. vw_supply_advice - Replenishment Recommendations

**Purpose**: Latest supply recommendations from planning algorithm

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `d` | date | Recommendation date |
| `sku_id` | int | SKU identifier |
| `article` | string | Article/SKU code |
| `warehouse_id` | int | Warehouse ID |
| `warehouse` | string | Warehouse name |
| `window_days` | int | Planning horizon (14/28 days) |
| `recommended_qty` | int | Recommended order quantity |
| `rationale_hash` | string | Explanation hash |

**Use case**: Track replenishment recommendations over time

### 4. vw_pricing_advice - Price Recommendations

**Purpose**: Latest pricing recommendations with elasticity insights

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `d` | date | Recommendation date |
| `sku_id` | int | SKU identifier |
| `article` | string | Article/SKU code |
| `suggested_price` | float | Recommended price |
| `suggested_discount_pct` | float | Suggested discount % |
| `expected_profit` | float | Expected profit at new price |
| `quality` | string | Quality indicator (low/medium) |
| `reason_code` | string | Reason code |
| `rationale_hash` | string | Explanation hash |

**Filtering**: Filter by `quality = 'medium'` for high-confidence recommendations

### 5. vw_reviews_summary - Review Aggregates

**Purpose**: Daily review statistics by SKU and marketplace

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `marketplace` | string | Marketplace (WB/OZON) |
| `sku_id` | int | SKU identifier |
| `article` | string | Article/SKU code |
| `d` | date | Review date |
| `reviews_total` | int | Total reviews |
| `rating_avg` | float | Average rating |
| `replies_sent` | int | Replies sent count |

## REST API Endpoints

### P&L Export

**GET** `/api/v1/export/bi/pnl.csv` or `.xlsx`

**Query Parameters**:
- `date_from` (required): Start date (YYYY-MM-DD)
- `date_to` (required): End date (YYYY-MM-DD)
- `sku_id` (optional): Filter by SKU
- `warehouse_id` (optional): Filter by warehouse
- `marketplace` (optional): Filter by marketplace (WB/OZON)
- `limit` (optional): Max rows (default 5000, max 100000)
- `offset` (optional): Pagination offset

**Example**:
```bash
curl "https://api.sovani.ru/api/v1/export/bi/pnl.csv?date_from=2025-09-01&date_to=2025-09-30&marketplace=WB" \
  -H "X-Telegram-Init-Data: ..." \
  -o pnl_september.csv
```

### Inventory Export

**GET** `/api/v1/export/bi/inventory.csv` or `.xlsx`

**Query Parameters**:
- `sku_id` (optional): Filter by SKU
- `warehouse_id` (optional): Filter by warehouse
- `limit` (optional): Max rows
- `offset` (optional): Pagination offset

### Supply Advice Export

**GET** `/api/v1/export/bi/supply_advice.csv` or `.xlsx`

**Query Parameters**:
- `sku_id` (optional): Filter by SKU
- `warehouse_id` (optional): Filter by warehouse
- `window_days` (optional): Filter by planning window (14/28)
- `limit` (optional): Max rows
- `offset` (optional): Pagination offset

### Pricing Advice Export

**GET** `/api/v1/export/bi/pricing_advice.csv` or `.xlsx`

**Query Parameters**:
- `sku_id` (optional): Filter by SKU
- `quality` (optional): Filter by quality (low/medium)
- `limit` (optional): Max rows
- `offset` (optional): Pagination offset

### Reviews Summary Export

**GET** `/api/v1/export/bi/reviews_summary.csv` or `.xlsx`

**Query Parameters**:
- `date_from` (optional): Start date
- `date_to` (optional): End date
- `sku_id` (optional): Filter by SKU
- `marketplace` (optional): Filter by marketplace
- `limit` (optional): Max rows
- `offset` (optional): Pagination offset

## Power BI Setup

### 1. Connect to PostgreSQL

1. Open Power BI Desktop
2. **Get Data** → **PostgreSQL database**
3. Enter connection details:
   - Server: `your-database-host:5432`
   - Database: `sovani`
4. Credentials: Username `bi_reader`, password from ops
5. Select tables/views to import

### 2. Import Views

Choose from:
- `vw_pnl_daily` (fact table)
- `vw_inventory_snapshot` (dimension)
- `vw_supply_advice` (dimension)
- `vw_pricing_advice` (dimension)
- `vw_reviews_summary` (fact table)

### 3. Create Relationships

**Model view**:
- `vw_pnl_daily[sku_id]` → `vw_pricing_advice[sku_id]`
- `vw_pnl_daily[sku_id]` → `vw_inventory_snapshot[sku_id]`
- `vw_pnl_daily[warehouse_id]` → `vw_inventory_snapshot[warehouse_id]`

### 4. Incremental Refresh

For large datasets, configure incremental refresh on `vw_pnl_daily`:

1. Power Query → Advanced Editor
2. Add parameters:
   ```m
   let
       RangeStart = DateTime.From(DateTime.LocalNow() - #duration(90, 0, 0, 0)),
       RangeEnd = DateTime.From(DateTime.LocalNow()),
       Source = PostgreSQL.Database("host", "sovani"),
       FilteredRows = Table.SelectRows(Source,
           each [d] >= RangeStart and [d] <= RangeEnd)
   in
       FilteredRows
   ```
3. Enable incremental refresh: Keep 90 days, refresh 7 days

## Metabase Setup

### 1. Add Database

1. **Admin** → **Databases** → **Add database**
2. Database type: **PostgreSQL**
3. Settings:
   - Name: `SoVAni Analytics`
   - Host: `your-database-host`
   - Port: `5432`
   - Database name: `sovani`
   - Username: `bi_reader`
   - Password: `***`
4. Click **Save**

### 2. Create Questions

**Example: Weekly Sales Trend**
```sql
SELECT
    DATE_TRUNC('week', d) AS week,
    marketplace,
    SUM(units) AS units_sold,
    SUM(profit_approx) AS profit
FROM vw_pnl_daily
WHERE d >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
```

**Example: Low Stock Alert**
```sql
SELECT
    i.sku_id,
    s.article,
    i.warehouse,
    i.on_hand,
    p.sv14 AS velocity_14d,
    CAST(i.on_hand / NULLIF(p.sv14, 0) AS INT) AS days_of_stock
FROM vw_inventory_snapshot i
JOIN vw_pnl_daily p ON p.sku_id = i.sku_id
    AND p.d = (SELECT MAX(d) FROM vw_pnl_daily)
JOIN sku s ON s.id = i.sku_id
WHERE i.on_hand < p.sv14 * 7  -- Less than 7 days stock
ORDER BY days_of_stock ASC;
```

### 3. Dashboard Templates

Create dashboards with:
- **Sales Overview**: Units, revenue, profit by marketplace
- **Inventory Health**: Stock levels, days of stock, stockouts
- **Pricing Insights**: Price recommendations by expected profit
- **Review Performance**: Rating trends, reply rate

## Data Limitations

### Wildberries API Constraint

**Important**: WB API provides maximum 176 days of historical data.

**Strategy**:
1. Historical data (>176 days): Use accumulated data in our database
2. Recent data (<176 days): Can be refreshed from WB API
3. Always rely on local database as source of truth

### Incremental Loading

For optimal performance:
- **Full refresh**: Run monthly for all views
- **Incremental**: Daily refresh for last 7 days on `vw_pnl_daily`
- **Snapshot views**: Refresh daily (they show latest state)

**Power BI M Query Example**:
```m
let
    LastRefresh = List.Max(vw_pnl_daily[d]),
    Source = PostgreSQL.Database("host", "sovani"),
    FilterNew = Table.SelectRows(Source, each [d] > LastRefresh)
in
    FilterNew
```

## Performance Tips

1. **Use Views**: Prefer views over direct table queries
2. **Filter Early**: Apply date filters at source (not in BI tool)
3. **Limit Rows**: Use `limit` parameter for exports (default 5000, max 100000)
4. **Index Usage**: Views are optimized with proper join order
5. **Caching**: REST API responses are cached for 5 minutes

## Troubleshooting

### Connection Refused
- Check firewall rules for port 5432
- Verify `bi_reader` credentials
- Ensure database SSL is configured

### Slow Queries
- Add date range filters: `WHERE d >= '2025-09-01'`
- Reduce limit: `?limit=1000`
- Check view indexes

### Missing Data
- Verify data exists: `SELECT COUNT(*) FROM vw_pnl_daily WHERE d = '2025-09-15';`
- Check date format: Use `YYYY-MM-DD`
- WB historical limit: Only 176 days available from API

## Support

For BI integration issues:
- Check logs: `/var/log/sovani-bot/`
- API docs: `https://api.sovani.ru/docs`
- Contact: dev team via Telegram
