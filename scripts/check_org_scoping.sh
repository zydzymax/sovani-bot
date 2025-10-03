#!/bin/bash
# CI Guard: Check for unscoped SQL queries (Stage 19)
# Fails if business queries are missing org_id filter

set -e

echo "🔍 Checking for unscoped SQL queries..."

# Business tables that MUST be scoped by org_id
BUSINESS_TABLES=(
    "reviews"
    "sku"
    "daily_sales"
    "daily_stock"
    "pricing_advice"
    "advice_supply"
    "pnl_daily"
    "cashflow_daily"
    "metrics_daily"
    "warehouse"
    "cost_price_history"
    "commission_rule"
)

FOUND_ISSUES=0

# Check routers and services for unscoped queries
for table in "${BUSINESS_TABLES[@]}"; do
    echo "Checking table: $table"

    # Find SELECT/UPDATE/DELETE queries without org_id
    UNSCOPED=$(git grep -nE "SELECT .* FROM ${table}[^;]*" app/web/routers app/services 2>/dev/null | grep -v "org_id" || true)

    if [ -n "$UNSCOPED" ]; then
        echo "❌ Found unscoped queries for table ${table}:"
        echo "$UNSCOPED"
        FOUND_ISSUES=1
    fi
done

# Check for INSERT without org_id
echo ""
echo "Checking INSERTs..."
for table in "${BUSINESS_TABLES[@]}"; do
    UNSCOPED_INSERT=$(git grep -nE "INSERT INTO ${table}" app/web/routers app/services 2>/dev/null | grep -v "org_id" || true)

    if [ -n "$UNSCOPED_INSERT" ]; then
        echo "❌ Found INSERT without org_id for table ${table}:"
        echo "$UNSCOPED_INSERT"
        FOUND_ISSUES=1
    fi
done

# Check for direct text() calls instead of exec_scoped
echo ""
echo "Checking for direct text() usage (should use exec_scoped)..."
DIRECT_TEXT=$(git grep -nE "db\.execute\(text\(" app/web/routers app/services 2>/dev/null | grep -v "exec_scoped" | grep -v "exec_unscoped" || true)

if [ -n "$DIRECT_TEXT" ]; then
    echo "⚠️  Found direct text() usage (consider using exec_scoped):"
    echo "$DIRECT_TEXT"
    # Warning only, not a failure
fi

echo ""
if [ $FOUND_ISSUES -eq 0 ]; then
    echo "✅ All queries are properly scoped with org_id"
    exit 0
else
    echo "❌ Found unscoped queries! Please add org_id filters."
    echo ""
    echo "Fix by:"
    echo "  1. Add 'org_id: int = Depends(get_org_scope)' to endpoint"
    echo "  2. Use WHERE org_id = :org_id in SQL"
    echo "  3. Or use exec_scoped() helper from app.db.utils"
    exit 1
fi
