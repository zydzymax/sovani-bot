"""stage16 cashflow and pnl schema

Revision ID: f54e77fed756
Revises: 29df4de99cf4
Create Date: 2025-10-02 18:20:33.993885

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f54e77fed756"
down_revision: Union[str, None] = "29df4de99cf4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create cashflow_daily table
    op.create_table(
        "cashflow_daily",
        sa.Column("d", sa.Date(), nullable=False),
        sa.Column("marketplace", sa.String(16), nullable=False),
        sa.Column("inflow", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("outflow", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("net", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("src_hash", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("d", "marketplace"),
    )
    op.create_index("ix_cashflow_daily_d", "cashflow_daily", ["d"])

    # 2. Create pnl_daily table
    op.create_table(
        "pnl_daily",
        sa.Column("d", sa.Date(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("marketplace", sa.String(16), nullable=False),
        sa.Column("revenue_net", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("cogs", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("gross_profit", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("refunds", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("delivery_cost", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("promo_cost", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("commissions", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("writeoffs", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("margin_pct", sa.Numeric(), nullable=True),
        sa.Column("src_hash", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("d", "sku_id", "marketplace"),
        sa.ForeignKeyConstraint(["sku_id"], ["sku.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_pnl_daily_d", "pnl_daily", ["d"])
    op.create_index("ix_pnl_daily_sku_id", "pnl_daily", ["sku_id"])

    # 3. Create views
    # vw_cashflow_daily - with cumulative balance (SQLite compatible via subquery)
    op.execute(
        """
        CREATE VIEW vw_cashflow_daily AS
        SELECT
            cf.d,
            cf.marketplace,
            cf.inflow,
            cf.outflow,
            cf.net,
            (SELECT SUM(cf2.net)
             FROM cashflow_daily cf2
             WHERE cf2.marketplace = cf.marketplace
               AND cf2.d <= cf.d) AS balance,
            cf.src_hash
        FROM cashflow_daily cf
        ORDER BY cf.d, cf.marketplace;
    """
    )

    # vw_pnl_actual_daily - with article info
    op.execute(
        """
        CREATE VIEW vw_pnl_actual_daily AS
        SELECT
            p.d,
            p.sku_id,
            s.article,
            p.marketplace,
            p.revenue_net,
            p.cogs,
            p.gross_profit,
            p.refunds,
            p.delivery_cost,
            p.promo_cost,
            p.commissions,
            p.writeoffs,
            p.margin_pct,
            p.src_hash
        FROM pnl_daily p
        JOIN sku s ON s.id = p.sku_id
        ORDER BY p.d DESC, p.sku_id;
    """
    )

    # vw_commission_recon - reconciliation view
    op.execute(
        """
        CREATE VIEW vw_commission_recon AS
        SELECT
            ds.d,
            ds.sku_id,
            s.article,
            s.marketplace,
            ds.commission_amount AS actual_commission,
            CASE
                WHEN cr.rate_pct IS NOT NULL
                THEN (ds.revenue_gross * cr.rate_pct / 100.0) + COALESCE(cr.fixed_per_unit * ds.qty, 0)
                ELSE ds.commission_amount
            END AS calc_commission,
            CASE
                WHEN cr.rate_pct IS NOT NULL
                THEN ds.commission_amount - ((ds.revenue_gross * cr.rate_pct / 100.0) + COALESCE(cr.fixed_per_unit * ds.qty, 0))
                ELSE 0
            END AS delta_abs,
            CASE
                WHEN cr.rate_pct IS NOT NULL AND ds.commission_amount > 0
                THEN (ds.commission_amount - ((ds.revenue_gross * cr.rate_pct / 100.0) + COALESCE(cr.fixed_per_unit * ds.qty, 0))) / ds.commission_amount * 100.0
                ELSE 0
            END AS delta_pct,
            CASE
                WHEN ABS(CASE
                    WHEN cr.rate_pct IS NOT NULL AND ds.commission_amount > 0
                    THEN (ds.commission_amount - ((ds.revenue_gross * cr.rate_pct / 100.0) + COALESCE(cr.fixed_per_unit * ds.qty, 0))) / ds.commission_amount * 100.0
                    ELSE 0
                END) > 5.0 THEN 1
                ELSE 0
            END AS flag_outlier
        FROM daily_sales ds
        JOIN sku s ON s.id = ds.sku_id
        LEFT JOIN commission_rules cr ON cr.marketplace = s.marketplace
            AND cr.category = s.article
            AND ds.d BETWEEN cr.effective_from AND COALESCE(cr.effective_until, DATE('9999-12-31'))
        WHERE ds.commission_amount > 0
        ORDER BY ds.d DESC, ds.sku_id;
    """
    )


def downgrade() -> None:
    # Drop views first
    op.execute("DROP VIEW IF EXISTS vw_commission_recon;")
    op.execute("DROP VIEW IF EXISTS vw_pnl_actual_daily;")
    op.execute("DROP VIEW IF EXISTS vw_cashflow_daily;")

    # Drop tables
    op.drop_index("ix_pnl_daily_sku_id", "pnl_daily")
    op.drop_index("ix_pnl_daily_d", "pnl_daily")
    op.drop_table("pnl_daily")

    op.drop_index("ix_cashflow_daily_d", "cashflow_daily")
    op.drop_table("cashflow_daily")
