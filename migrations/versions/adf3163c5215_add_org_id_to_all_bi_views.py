"""add_org_id_to_all_bi_views

Revision ID: adf3163c5215
Revises: 130f3aadec77
Create Date: 2025-10-03 22:18:34.626620

Recreates all BI views with org_id column for multi-tenant isolation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "adf3163c5215"
down_revision: Union[str, None] = "130f3aadec77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate all BI views with org_id column."""

    # Drop all existing views first
    op.execute("DROP VIEW IF EXISTS vw_reviews_summary;")
    op.execute("DROP VIEW IF EXISTS vw_pricing_advice;")
    op.execute("DROP VIEW IF EXISTS vw_supply_advice;")
    op.execute("DROP VIEW IF EXISTS vw_inventory_snapshot;")
    op.execute("DROP VIEW IF EXISTS vw_pnl_daily;")
    op.execute("DROP VIEW IF EXISTS vw_cashflow_daily;")
    op.execute("DROP VIEW IF EXISTS vw_pnl_actual_daily;")
    op.execute("DROP VIEW IF EXISTS vw_commission_recon;")
    op.execute("DROP VIEW IF EXISTS vw_reviews_sla;")
    op.execute("DROP VIEW IF EXISTS vw_ops_health;")
    op.execute("DROP VIEW IF EXISTS vw_slo_daily;")
    op.execute("DROP VIEW IF EXISTS cost_price_latest;")

    # Recreate cost_price_latest helper view WITH org_id
    op.execute(
        """
        CREATE VIEW cost_price_latest AS
        SELECT
            cph.org_id,
            cph.sku_id,
            cph.cost_price AS unit_cost,
            cph.dt_from
        FROM cost_price_history cph
        INNER JOIN (
            SELECT org_id, sku_id, MAX(dt_from) AS max_dt
            FROM cost_price_history
            GROUP BY org_id, sku_id
        ) latest ON cph.org_id = latest.org_id
                AND cph.sku_id = latest.sku_id
                AND cph.dt_from = latest.max_dt
    """
    )

    # 1. vw_pnl_daily - Daily P&L by SKU/warehouse/marketplace (WITH org_id)
    op.execute(
        """
        CREATE VIEW vw_pnl_daily AS
        SELECT
            ds.org_id,
            DATE(ds.d) AS d,
            s.id AS sku_id,
            s.article AS article,
            w.id AS warehouse_id,
            w.name AS warehouse,
            s.marketplace AS marketplace,
            ds.qty AS units,
            (ds.revenue_gross - ds.refunds_amount) AS revenue_net_gross,
            (ds.revenue_gross - ds.refunds_amount
                - ds.promo_cost - ds.delivery_cost
                - ds.commission_amount) AS revenue_net,
            COALESCE(cp.unit_cost, 0) AS unit_cost,
            MAX(
                (ds.revenue_gross - ds.refunds_amount
                    - ds.promo_cost - ds.delivery_cost
                    - ds.commission_amount) - ds.qty * COALESCE(cp.unit_cost, 0),
                0
            ) AS profit_approx,
            md.sv14,
            md.sv28
        FROM daily_sales ds
        JOIN sku s ON s.id = ds.sku_id AND s.org_id = ds.org_id
        LEFT JOIN warehouse w ON w.id = ds.warehouse_id AND w.org_id = ds.org_id
        LEFT JOIN metrics_daily md ON md.sku_id = ds.sku_id
                                   AND md.d = ds.d
                                   AND md.org_id = ds.org_id
        LEFT JOIN cost_price_latest cp ON cp.sku_id = ds.sku_id
                                       AND cp.org_id = ds.org_id
    """
    )

    # 2. vw_inventory_snapshot - Latest inventory by SKU/warehouse (WITH org_id)
    op.execute(
        """
        CREATE VIEW vw_inventory_snapshot AS
        SELECT
            st.org_id,
            st.sku_id,
            st.warehouse_id,
            w.name AS warehouse,
            st.on_hand,
            st.in_transit,
            DATE(st.d) AS d
        FROM daily_stock st
        LEFT JOIN warehouse w ON w.id = st.warehouse_id AND w.org_id = st.org_id
        INNER JOIN (
            SELECT org_id, sku_id, warehouse_id, MAX(d) AS max_d
            FROM daily_stock
            GROUP BY org_id, sku_id, warehouse_id
        ) latest ON st.org_id = latest.org_id
                AND st.sku_id = latest.sku_id
                AND st.warehouse_id = latest.warehouse_id
                AND st.d = latest.max_d
    """
    )

    # 3. vw_supply_advice - Latest supply planning advice (WITH org_id)
    op.execute(
        """
        CREATE VIEW vw_supply_advice AS
        SELECT
            adv.org_id,
            adv.d AS advice_date,
            adv.sku_id,
            s.article,
            s.marketplace,
            adv.warehouse_id,
            w.name AS warehouse,
            adv.recommended_qty,
            adv.rationale_hash
        FROM advice_supply adv
        JOIN sku s ON s.id = adv.sku_id AND s.org_id = adv.org_id
        LEFT JOIN warehouse w ON w.id = adv.warehouse_id AND w.org_id = adv.org_id
        INNER JOIN (
            SELECT org_id, MAX(d) AS max_d
            FROM advice_supply
            GROUP BY org_id
        ) latest ON adv.org_id = latest.org_id AND adv.d = latest.max_d
    """
    )

    # 4. vw_pricing_advice - Latest pricing recommendations (WITH org_id)
    op.execute(
        """
        CREATE VIEW vw_pricing_advice AS
        SELECT
            pa.org_id,
            pa.d AS advice_date,
            pa.sku_id,
            s.article,
            s.marketplace,
            pa.suggested_price,
            pa.suggested_discount_pct,
            pa.expected_profit,
            pa.quality,
            pa.rationale_hash,
            pa.reason_code
        FROM pricing_advice pa
        JOIN sku s ON s.id = pa.sku_id AND s.org_id = pa.org_id
        INNER JOIN (
            SELECT org_id, MAX(d) AS max_d
            FROM pricing_advice
            GROUP BY org_id
        ) latest ON pa.org_id = latest.org_id AND pa.d = latest.max_d
    """
    )

    # 5. vw_reviews_summary - Reviews summary with SLA metrics (WITH org_id)
    op.execute(
        """
        CREATE VIEW vw_reviews_summary AS
        SELECT
            r.org_id,
            r.marketplace,
            COUNT(*) AS total_reviews,
            AVG(r.rating) AS avg_rating,
            SUM(CASE WHEN r.reply_status = 'sent' THEN 1 ELSE 0 END) AS replied_count,
            CAST(SUM(CASE WHEN r.reply_status = 'sent' THEN 1 ELSE 0 END) AS FLOAT) /
                NULLIF(COUNT(*), 0) * 100 AS reply_rate_pct
        FROM reviews r
        GROUP BY r.org_id, r.marketplace
    """
    )

    # 6. vw_cashflow_daily - Daily cashflow (WITH org_id)
    op.execute(
        """
        CREATE VIEW vw_cashflow_daily AS
        SELECT
            org_id,
            d,
            marketplace,
            inflow,
            outflow,
            net
        FROM cashflow_daily
    """
    )

    # 7. vw_pnl_actual_daily - Actual P&L from computed table (WITH org_id)
    op.execute(
        """
        CREATE VIEW vw_pnl_actual_daily AS
        SELECT
            pnl.org_id,
            pnl.d,
            pnl.sku_id,
            s.article,
            s.marketplace,
            pnl.revenue_net,
            pnl.cogs,
            pnl.gross_profit,
            pnl.margin_pct
        FROM pnl_daily pnl
        JOIN sku s ON s.id = pnl.sku_id AND s.org_id = pnl.org_id
    """
    )

    # 8. vw_commission_recon - Commission reconciliation (WITH org_id)
    # NOTE: Only create if commission_reconciliation table exists
    try:
        op.execute(
            """
            CREATE VIEW vw_commission_recon AS
            SELECT
                org_id,
                d,
                sku_id,
                commission_actual,
                commission_calculated,
                delta,
                delta_pct,
                flag_outlier
            FROM commission_reconciliation
        """
        )
    except Exception:
        pass  # Table doesn't exist yet

    # 9. vw_reviews_sla - Reviews SLA tracking (WITH org_id)
    op.execute(
        """
        CREATE VIEW vw_reviews_sla AS
        SELECT
            r.org_id,
            r.review_id,
            r.marketplace,
            r.rating,
            r.created_at_utc,
            r.first_reply_at_utc,
            r.reply_status,
            r.reply_kind,
            CASE
                WHEN r.first_reply_at_utc IS NOT NULL THEN
                    CAST((julianday(r.first_reply_at_utc) - julianday(r.created_at_utc)) * 24 AS REAL)
                ELSE NULL
            END AS ttfr_hours,
            CASE
                WHEN r.first_reply_at_utc IS NULL
                     AND CAST((julianday('now') - julianday(r.created_at_utc)) * 24 AS REAL) > 24
                THEN 1
                ELSE 0
            END AS is_overdue
        FROM reviews r
    """
    )

    # 10. vw_ops_health - Operational health summary (WITH org_id)
    # NOTE: Only create if ops_detector_runs table exists
    try:
        op.execute(
            """
            CREATE VIEW vw_ops_health AS
            SELECT
                org_id,
                detector_name,
                last_run_at,
                check_result,
                severity,
                message
            FROM ops_detector_runs
            WHERE last_run_at >= datetime('now', '-1 hour')
        """
        )
    except Exception:
        pass  # Table doesn't exist yet

    # 11. vw_slo_daily - SLO compliance tracking (WITH org_id)
    # NOTE: Only create if slo_tracking table exists
    try:
        op.execute(
            """
            CREATE VIEW vw_slo_daily AS
            SELECT
                org_id,
                d,
                slo_name,
                target_pct,
                actual_pct,
                in_compliance,
                breach_count
            FROM slo_tracking
        """
        )
    except Exception:
        pass  # Table doesn't exist yet


def downgrade() -> None:
    """Drop all BI views."""
    op.execute("DROP VIEW IF EXISTS vw_slo_daily;")
    op.execute("DROP VIEW IF EXISTS vw_ops_health;")
    op.execute("DROP VIEW IF EXISTS vw_reviews_sla;")
    op.execute("DROP VIEW IF EXISTS vw_commission_recon;")
    op.execute("DROP VIEW IF EXISTS vw_pnl_actual_daily;")
    op.execute("DROP VIEW IF EXISTS vw_cashflow_daily;")
    op.execute("DROP VIEW IF EXISTS vw_reviews_summary;")
    op.execute("DROP VIEW IF EXISTS vw_pricing_advice;")
    op.execute("DROP VIEW IF EXISTS vw_supply_advice;")
    op.execute("DROP VIEW IF EXISTS vw_inventory_snapshot;")
    op.execute("DROP VIEW IF EXISTS vw_pnl_daily;")
    op.execute("DROP VIEW IF EXISTS cost_price_latest;")
