"""Actual P&L calculation with cost strategies."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.core.config import get_settings


def get_unit_cost(db: Session, sku_id: int, d: date, strategy: str = "latest") -> float:
    """Get unit cost for SKU on date using specified strategy."""
    from app.db.models import CostPriceHistory

    if strategy == "latest":
        # Latest cost before or on date
        stmt = (
            select(CostPriceHistory.cost_price)
            .where(CostPriceHistory.sku_id == sku_id, CostPriceHistory.dt_from <= d)
            .order_by(CostPriceHistory.dt_from.desc())
            .limit(1)
        )
        result = db.execute(stmt).scalar()
        return float(result) if result else 0.0

    elif strategy == "moving_avg_28":
        # 28-day moving average
        d_start = d - timedelta(days=28)
        stmt = select(func.avg(CostPriceHistory.cost_price)).where(
            CostPriceHistory.sku_id == sku_id, CostPriceHistory.dt_from.between(d_start, d)
        )
        result = db.execute(stmt).scalar()
        return float(result) if result else 0.0

    return 0.0


def compute_daily_pnl(
    db: Session, d_from: date, d_to: date, cost_strategy: str = "latest"
) -> list[dict]:
    """Compute actual daily P&L."""
    from app.db.models import SKU, DailySales

    settings = get_settings()

    results = []

    # Query sales data
    stmt = (
        select(DailySales, SKU.marketplace, SKU.article)
        .join(SKU, DailySales.sku_id == SKU.id)
        .where(DailySales.d.between(d_from, d_to))
        .order_by(DailySales.d, DailySales.sku_id)
    )

    rows = db.execute(stmt).all()

    for row in rows:
        ds = row[0]
        marketplace = row[1]

        # Get cost
        unit_cost = get_unit_cost(db, ds.sku_id, ds.d, cost_strategy)
        cogs = ds.qty * unit_cost

        # Calculate revenue components
        revenue_net = (
            ds.revenue_gross
            - ds.refunds_amount
            - ds.promo_cost
            - ds.delivery_cost
            - ds.commission_amount
        )

        gross_profit = revenue_net - cogs
        margin_pct = (gross_profit / revenue_net * 100) if revenue_net > 0 else 0

        # Hash for idempotency
        src_data = f"{ds.d}|{ds.sku_id}|{marketplace}|{revenue_net:.2f}|{cogs:.2f}"
        src_hash = hashlib.sha256(src_data.encode()).hexdigest()

        results.append(
            {
                "d": ds.d,
                "sku_id": ds.sku_id,
                "marketplace": marketplace,
                "revenue_net": round(revenue_net, 2),
                "cogs": round(cogs, 2),
                "gross_profit": round(gross_profit, 2),
                "refunds": round(ds.refunds_amount, 2),
                "delivery_cost": round(ds.delivery_cost, 2),
                "promo_cost": round(ds.promo_cost, 2),
                "commissions": round(ds.commission_amount, 2),
                "writeoffs": 0.0,  # Can be extended
                "margin_pct": round(margin_pct, 2),
                "src_hash": src_hash,
            }
        )

    return results


def upsert_pnl_daily(db: Session, records: list[dict]) -> int:
    """Upsert P&L records."""
    from sqlalchemy import Table

    from app.db.models import Base

    metadata = Base.metadata
    pnl_table = Table("pnl_daily", metadata, autoload_with=db.get_bind())

    count = 0
    for rec in records:
        stmt = select(pnl_table).where(
            pnl_table.c.d == rec["d"],
            pnl_table.c.sku_id == rec["sku_id"],
            pnl_table.c.marketplace == rec["marketplace"],
        )
        existing = db.execute(stmt).first()

        if existing:
            if existing.src_hash != rec["src_hash"]:
                db.execute(
                    pnl_table.update()
                    .where(
                        pnl_table.c.d == rec["d"],
                        pnl_table.c.sku_id == rec["sku_id"],
                        pnl_table.c.marketplace == rec["marketplace"],
                    )
                    .values(
                        **{k: v for k, v in rec.items() if k not in ["d", "sku_id", "marketplace"]}
                    )
                )
                count += 1
        else:
            db.execute(pnl_table.insert().values(**rec))
            count += 1

    db.commit()
    return count
