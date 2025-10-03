"""stage19_multi_tenant_orgs_users_rbac_scoping

Revision ID: 130f3aadec77
Revises: 96a2ffdd5b16
Create Date: 2025-10-02 22:24:26.565730

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "130f3aadec77"
down_revision: Union[str, None] = "96a2ffdd5b16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Multi-tenant migration: organizations, users, RBAC, org_id scoping."""

    # =========================================================================
    # 1. Create organizations table
    # =========================================================================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # =========================================================================
    # 2. Create users table
    # =========================================================================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER NOT NULL UNIQUE,
            tg_username TEXT,
            tg_first_name TEXT,
            tg_last_name TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # =========================================================================
    # 3. Create org_members table with RBAC
    # =========================================================================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS org_members (
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('owner', 'manager', 'viewer')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, user_id)
        )
    """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_org_members_user_id ON org_members(user_id)")

    # =========================================================================
    # 4. Create org_credentials table (marketplace tokens per org)
    # =========================================================================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS org_credentials (
            org_id INTEGER PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
            wb_feedbacks_token TEXT,
            wb_ads_token TEXT,
            wb_stats_token TEXT,
            wb_supply_token TEXT,
            wb_analytics_token TEXT,
            wb_content_token TEXT,
            ozon_client_id TEXT,
            ozon_api_key_admin TEXT,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # =========================================================================
    # 5. Create default organization and backfill
    # =========================================================================
    op.execute(
        """
        INSERT OR IGNORE INTO organizations (id, name, created_at)
        VALUES (1, 'SoVAni Default', CURRENT_TIMESTAMP)
    """
    )

    # =========================================================================
    # 6. Add org_id to all business tables
    # =========================================================================

    # List of all business tables that need org_id
    business_tables = [
        "sku",
        "warehouse",
        "cost_price_history",
        "commission_rule",
        "daily_sales",
        "daily_stock",
        "reviews",
        "cashflow",
        "metrics_daily",
        "advice_supply",
        "pricing_advice",
        "pnl_daily",
        "cashflow_daily",
    ]

    for table in business_tables:
        # Check if table exists before altering
        result = (
            op.get_bind()
            .execute(
                text(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
            )
            .fetchone()
        )

        if not result or result[0] == 0:
            continue

        # Check if org_id column already exists
        col_check = op.get_bind().execute(text(f"PRAGMA table_info({table})")).fetchall()

        has_org_id = any(col[1] == "org_id" for col in col_check)

        if not has_org_id:
            # Add org_id column (nullable first)
            op.execute(text(f"ALTER TABLE {table} ADD COLUMN org_id INTEGER"))

            # Backfill with default org
            op.execute(text(f"UPDATE {table} SET org_id = 1"))

        # Note: SQLite doesn't support ADD CONSTRAINT after table creation
        # NOT NULL enforcement will be done at application level

    # =========================================================================
    # 7. Create indexes on org_id (only for tables that exist and have org_id)
    # =========================================================================

    # Helper to safely create index only if table exists
    def create_index_if_table_exists(table_name: str, index_sql: str) -> None:
        result = (
            op.get_bind()
            .execute(
                text(
                    f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                )
            )
            .fetchone()
        )
        if result and result[0] > 0:
            op.execute(index_sql)

    # Core reference tables
    create_index_if_table_exists("sku", "CREATE INDEX IF NOT EXISTS idx_sku_org_id ON sku(org_id)")
    create_index_if_table_exists(
        "warehouse", "CREATE INDEX IF NOT EXISTS idx_warehouse_org_id ON warehouse(org_id)"
    )
    create_index_if_table_exists(
        "cost_price_history",
        "CREATE INDEX IF NOT EXISTS idx_cost_price_history_org_sku ON cost_price_history(org_id, sku_id)",
    )
    create_index_if_table_exists(
        "commission_rule",
        "CREATE INDEX IF NOT EXISTS idx_commission_rule_org_id ON commission_rule(org_id)",
    )

    # Fact tables with date
    create_index_if_table_exists(
        "daily_sales",
        "CREATE INDEX IF NOT EXISTS idx_daily_sales_org_date ON daily_sales(org_id, d)",
    )
    create_index_if_table_exists(
        "daily_stock",
        "CREATE INDEX IF NOT EXISTS idx_daily_stock_org_date ON daily_stock(org_id, d)",
    )
    create_index_if_table_exists(
        "cashflow",
        "CREATE INDEX IF NOT EXISTS idx_cashflow_org_date ON cashflow(org_id, event_date)",
    )
    create_index_if_table_exists(
        "metrics_daily",
        "CREATE INDEX IF NOT EXISTS idx_metrics_daily_org_date ON metrics_daily(org_id, d)",
    )

    # Reviews
    create_index_if_table_exists(
        "reviews",
        "CREATE INDEX IF NOT EXISTS idx_reviews_org_created ON reviews(org_id, created_at_utc)",
    )

    # Advice tables
    create_index_if_table_exists(
        "advice_supply",
        "CREATE INDEX IF NOT EXISTS idx_advice_supply_org_sku ON advice_supply(org_id, sku_id)",
    )
    create_index_if_table_exists(
        "pricing_advice",
        "CREATE INDEX IF NOT EXISTS idx_pricing_advice_org_sku ON pricing_advice(org_id, sku_id)",
    )

    # PnL & Cashflow (if exist)
    create_index_if_table_exists(
        "pnl_daily", "CREATE INDEX IF NOT EXISTS idx_pnl_daily_org_date ON pnl_daily(org_id, d)"
    )
    create_index_if_table_exists(
        "cashflow_daily",
        "CREATE INDEX IF NOT EXISTS idx_cashflow_daily_org_date ON cashflow_daily(org_id, d)",
    )

    # =========================================================================
    # 8. Create org_limits_state table for rate limiting
    # =========================================================================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS org_limits_state (
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            limit_key TEXT NOT NULL,
            ts_bucket INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (org_id, limit_key, ts_bucket)
        )
    """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_org_limits_bucket ON org_limits_state(ts_bucket)")


def downgrade() -> None:
    """Rollback multi-tenant schema."""

    # Drop limits table
    op.execute("DROP TABLE IF EXISTS org_limits_state")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_cashflow_daily_org_date")
    op.execute("DROP INDEX IF EXISTS idx_pnl_daily_org_date")
    op.execute("DROP INDEX IF EXISTS idx_pricing_advice_org_sku")
    op.execute("DROP INDEX IF EXISTS idx_advice_supply_org_sku")
    op.execute("DROP INDEX IF EXISTS idx_reviews_org_created")
    op.execute("DROP INDEX IF EXISTS idx_metrics_daily_org_date")
    op.execute("DROP INDEX IF EXISTS idx_cashflow_org_date")
    op.execute("DROP INDEX IF EXISTS idx_daily_stock_org_date")
    op.execute("DROP INDEX IF EXISTS idx_daily_sales_org_date")
    op.execute("DROP INDEX IF EXISTS idx_commission_rule_org_id")
    op.execute("DROP INDEX IF EXISTS idx_cost_price_history_org_sku")
    op.execute("DROP INDEX IF EXISTS idx_warehouse_org_id")
    op.execute("DROP INDEX IF EXISTS idx_sku_org_id")

    # Remove org_id columns (SQLite doesn't support DROP COLUMN in old versions)
    # This is destructive - in production, you'd need to recreate tables
    business_tables = [
        "sku",
        "warehouse",
        "cost_price_history",
        "commission_rule",
        "daily_sales",
        "daily_stock",
        "reviews",
        "cashflow",
        "metrics_daily",
        "advice_supply",
        "pricing_advice",
        "pnl_daily",
        "cashflow_daily",
    ]

    for table in business_tables:
        # SQLite limitation: can't drop column easily
        # This is a placeholder - real rollback would need table recreation
        pass

    # Drop multi-tenant tables
    op.execute("DROP TABLE IF EXISTS org_credentials")
    op.execute("DROP INDEX IF EXISTS idx_org_members_user_id")
    op.execute("DROP TABLE IF EXISTS org_members")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS organizations")
