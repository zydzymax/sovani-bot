"""BI views for PnL, Inventory, Supply, Pricing, Reviews

Revision ID: 29df4de99cf4
Revises: 1f44d27e3ab6
Create Date: 2025-10-02 17:49:55.380539

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "29df4de99cf4"
down_revision: Union[str, None] = "1f44d27e3ab6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing views if they exist (for idempotency)
    op.execute("DROP VIEW IF EXISTS vw_reviews_summary;")
    op.execute("DROP VIEW IF EXISTS vw_pricing_advice;")
    op.execute("DROP VIEW IF EXISTS vw_supply_advice;")
    op.execute("DROP VIEW IF EXISTS vw_inventory_snapshot;")
    op.execute("DROP VIEW IF EXISTS vw_pnl_daily;")
    op.execute("DROP VIEW IF EXISTS cost_price_latest;")

    # Create helper view for latest cost price (SQLite compatible)
    op.execute(
        """
        CREATE VIEW cost_price_latest AS
        SELECT
            cph.sku_id,
            cph.cost_price AS unit_cost,
            cph.dt_from
        FROM cost_price_history cph
        INNER JOIN (
            SELECT sku_id, MAX(dt_from) AS max_dt
            FROM cost_price_history
            GROUP BY sku_id
        ) latest ON cph.sku_id = latest.sku_id AND cph.dt_from = latest.max_dt;
    """
    )

    # 1. vw_pnl_daily - Daily P&L by SKU/warehouse/marketplace
    op.execute(
        """
        CREATE VIEW vw_pnl_daily AS
        SELECT
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
        JOIN sku s ON s.id = ds.sku_id
        LEFT JOIN warehouse w ON w.id = ds.warehouse_id
        LEFT JOIN metrics_daily md ON md.sku_id = ds.sku_id AND md.d = ds.d
        LEFT JOIN cost_price_latest cp ON cp.sku_id = ds.sku_id;
    """
    )

    # 2. vw_inventory_snapshot - Latest inventory by SKU/warehouse
    op.execute(
        """
        CREATE VIEW vw_inventory_snapshot AS
        SELECT
            st.sku_id,
            st.warehouse_id,
            w.name AS warehouse,
            st.on_hand,
            st.in_transit,
            DATE(st.d) AS d
        FROM daily_stock st
        LEFT JOIN warehouse w ON w.id = st.warehouse_id
        INNER JOIN (
            SELECT sku_id, warehouse_id, MAX(d) AS max_d
            FROM daily_stock
            GROUP BY sku_id, warehouse_id
        ) latest ON st.sku_id = latest.sku_id
                AND st.warehouse_id = latest.warehouse_id
                AND st.d = latest.max_d;
    """
    )

    # 3. vw_supply_advice - Latest supply recommendations
    op.execute(
        """
        CREATE VIEW vw_supply_advice AS
        SELECT
            DATE(a.d) AS d,
            a.sku_id,
            s.article,
            a.warehouse_id,
            w.name AS warehouse,
            a.window_days,
            a.recommended_qty,
            a.rationale_hash
        FROM advice_supply a
        JOIN sku s ON s.id = a.sku_id
        LEFT JOIN warehouse w ON w.id = a.warehouse_id
        INNER JOIN (
            SELECT sku_id, warehouse_id, window_days, MAX(d) AS max_d
            FROM advice_supply
            GROUP BY sku_id, warehouse_id, window_days
        ) latest ON a.sku_id = latest.sku_id
                AND a.warehouse_id = latest.warehouse_id
                AND a.window_days = latest.window_days
                AND a.d = latest.max_d;
    """
    )

    # 4. vw_pricing_advice - Latest pricing recommendations
    op.execute(
        """
        CREATE VIEW vw_pricing_advice AS
        SELECT
            DATE(p.d) AS d,
            p.sku_id,
            s.article,
            p.suggested_price,
            p.suggested_discount_pct,
            p.expected_profit,
            p.quality,
            p.reason_code,
            p.rationale_hash
        FROM pricing_advice p
        JOIN sku s ON s.id = p.sku_id
        INNER JOIN (
            SELECT sku_id, MAX(d) AS max_d
            FROM pricing_advice
            GROUP BY sku_id
        ) latest ON p.sku_id = latest.sku_id AND p.d = latest.max_d;
    """
    )

    # 5. vw_reviews_summary - Daily review aggregates
    op.execute(
        """
        CREATE VIEW vw_reviews_summary AS
        SELECT
            r.marketplace,
            r.sku_id,
            s.article,
            DATE(r.created_at_utc) AS d,
            COUNT(*) AS reviews_total,
            AVG(CASE WHEN r.rating = 0 THEN NULL ELSE r.rating END) AS rating_avg,
            SUM(CASE WHEN r.reply_status = 'sent' THEN 1 ELSE 0 END) AS replies_sent
        FROM reviews r
        JOIN sku s ON s.id = r.sku_id
        GROUP BY r.marketplace, r.sku_id, s.article, DATE(r.created_at_utc);
    """
    )


def downgrade() -> None:
    # Drop views in reverse order
    op.execute("DROP VIEW IF EXISTS vw_reviews_summary;")
    op.execute("DROP VIEW IF EXISTS vw_pricing_advice;")
    op.execute("DROP VIEW IF EXISTS vw_supply_advice;")
    op.execute("DROP VIEW IF EXISTS vw_inventory_snapshot;")
    op.execute("DROP VIEW IF EXISTS vw_pnl_daily;")
    op.execute("DROP VIEW IF EXISTS cost_price_latest;")
