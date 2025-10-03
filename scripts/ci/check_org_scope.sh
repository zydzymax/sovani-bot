#!/bin/bash
# CI Guard: Prevent unscoped SQL queries from merging (Stage 19)
#
# This script scans all Python files for SQL queries that access business tables
# without proper org_id scoping. Fails the build if violations are found.
#
# Usage:
#   ./scripts/ci/check_org_scope.sh
#
# Returns:
#   0 - All checks passed
#   1 - Found unscoped queries or other violations

set -e

BUSINESS_TABLES=(
    "reviews"
    "sku"
    "daily_sales"
    "daily_stock"
    "cashflow"
    "pricing_advice"
    "advice_supply"
    "pnl_daily"
    "cashflow_daily"
    "metrics_daily"
    "warehouse"
    "cost_price_history"
)

FOUND_ISSUES=0

echo "🛡️  Stage 19: Multi-Tenant Org Scoping Guard"
echo "============================================="

# Check 1: SELECT queries without org_id filter
echo ""
echo "📋 Check 1: SELECT queries must filter by org_id"
echo "------------------------------------------------"

for table in "${BUSINESS_TABLES[@]}"; do
    # Find SELECT queries for this table that don't mention org_id
    # Exclude:
    # - Comments (lines starting with #)
    # - Migration files (they handle org_id specially)
    # - Test fixtures (they may setup test data)
    # - vw_ views (views should include org_id in their definition)

    UNSCOPED=$(git grep -nE "SELECT .* FROM ${table}[^;]*" \
        app/web/routers app/services \
        2>/dev/null \
        | grep -v "org_id" \
        | grep -v "^[[:space:]]*#" \
        | grep -v "migrations/" \
        | grep -v "test_" \
        || true)

    if [ -n "$UNSCOPED" ]; then
        echo "❌ Found unscoped SELECT for table '${table}':"
        echo "$UNSCOPED"
        echo ""
        FOUND_ISSUES=1
    fi
done

# Check 2: INSERT queries without org_id column
echo ""
echo "📋 Check 2: INSERT queries must include org_id"
echo "-----------------------------------------------"

for table in "${BUSINESS_TABLES[@]}"; do
    UNSCOPED_INSERTS=$(git grep -nE "INSERT INTO ${table}\s*\(" \
        app/web/routers app/services \
        2>/dev/null \
        | grep -v "org_id" \
        | grep -v "^[[:space:]]*#" \
        | grep -v "migrations/" \
        | grep -v "test_" \
        || true)

    if [ -n "$UNSCOPED_INSERTS" ]; then
        echo "❌ Found INSERT without org_id for table '${table}':"
        echo "$UNSCOPED_INSERTS"
        echo ""
        FOUND_ISSUES=1
    fi
done

# Check 3: Direct text() usage without exec_scoped()
echo ""
echo "📋 Check 3: Raw SQL should use exec_scoped()"
echo "--------------------------------------------"

# Find db.execute(text(...)) patterns that don't use exec_scoped
DIRECT_TEXT=$(git grep -nE "db\.execute\(text\(" \
    app/web/routers app/services \
    2>/dev/null \
    | grep -v "exec_scoped" \
    | grep -v "migrations/" \
    | grep -v "test_" \
    || true)

if [ -n "$DIRECT_TEXT" ]; then
    echo "⚠️  Warning: Direct text() usage found (prefer exec_scoped):"
    echo "$DIRECT_TEXT"
    echo ""
    # This is a warning, not a hard failure (some system queries may be OK)
fi

# Check 4: Routers without OrgScope dependency
echo ""
echo "📋 Check 4: Business routers should use OrgScope"
echo "------------------------------------------------"

# Find router files that query business tables but don't import OrgScope
for table in "${BUSINESS_TABLES[@]}"; do
    # Find files that have SELECT/INSERT/UPDATE for this table
    FILES_WITH_QUERIES=$(git grep -l "FROM ${table}" \
        app/web/routers/*.py \
        2>/dev/null \
        || true)

    for file in $FILES_WITH_QUERIES; do
        # Check if this file imports OrgScope
        HAS_ORGSCOPE=$(grep -E "from app.web.deps import.*OrgScope|import.*OrgScope" "$file" || true)

        if [ -z "$HAS_ORGSCOPE" ]; then
            echo "⚠️  Router ${file} queries '${table}' but doesn't import OrgScope"
            FOUND_ISSUES=1
        fi
    done
done

# Check 5: No "покупатель" word in reply templates
echo ""
echo "📋 Check 5: Reply templates must not use 'покупатель'"
echo "----------------------------------------------------"

POKUPATEL_USAGE=$(git grep -nE "покупатель|Покупатель" \
    app/ai/replies.py app/domain/reviews/templates.py \
    2>/dev/null \
    | grep -v "НЕ используй" \
    | grep -v "Never use" \
    | grep -v "already avoid" \
    | grep -v "# Comment" \
    || true)

if [ -n "$POKUPATEL_USAGE" ]; then
    echo "❌ Found forbidden 'покупатель' in templates:"
    echo "$POKUPATEL_USAGE"
    echo ""
    FOUND_ISSUES=1
fi

# Summary
echo ""
echo "============================================="
if [ $FOUND_ISSUES -eq 0 ]; then
    echo "✅ All org scoping checks PASSED"
    exit 0
else
    echo "❌ Org scoping violations found - see above"
    echo ""
    echo "Fix these issues before merging:"
    echo "  1. Add 'org_id: OrgScope' parameter to router endpoints"
    echo "  2. Use exec_scoped() for all business table queries"
    echo "  3. Include 'WHERE org_id = :org_id' in all SQL queries"
    echo "  4. Add org_id column to all INSERT statements"
    echo ""
    echo "See STAGE_19_SAFETY_BAR.md for patterns and examples."
    exit 1
fi
