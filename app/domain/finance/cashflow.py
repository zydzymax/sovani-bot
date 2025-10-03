"""Cashflow calculation from marketplace transactions."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.core.config import get_settings


def build_daily_cashflow(db: Session, d_from: date, d_to: date) -> list[dict]:
    """Build daily cashflow from sales data.

    Args:
        db: Database session
        d_from: Start date
        d_to: End date

    Returns:
        List of cashflow records with inflow, outflow, net

    Note:
        Uses sales data as approximation. In production, use actual payment data
        from marketplace APIs if available. Settlement lag is configurable.

    """
    from app.db.models import SKU, DailySales

    settings = get_settings()
    settlement_lag = settings.cf_default_settlement_lag_days

    results = []

    # Query aggregated sales by date and marketplace
    stmt = (
        select(
            DailySales.d,
            SKU.marketplace,
            func.sum(DailySales.revenue_gross - DailySales.refunds_amount).label("gross_revenue"),
            func.sum(DailySales.commission_amount).label("total_commission"),
            func.sum(DailySales.delivery_cost).label("total_delivery"),
            func.sum(DailySales.promo_cost).label("total_promo"),
            func.sum(DailySales.refunds_amount).label("total_refunds"),
        )
        .join(SKU, DailySales.sku_id == SKU.id)
        .where(DailySales.d.between(d_from, d_to))
        .group_by(DailySales.d, SKU.marketplace)
        .order_by(DailySales.d, SKU.marketplace)
    )

    rows = db.execute(stmt).all()

    for row in rows:
        d_sale = row.d
        marketplace = row.marketplace
        gross_revenue = float(row.gross_revenue or 0)
        total_commission = float(row.total_commission or 0)
        total_delivery = float(row.total_delivery or 0)
        total_promo = float(row.total_promo or 0)
        total_refunds = float(row.total_refunds or 0)

        # Approximate inflow: revenue arrives after settlement lag
        # Mark as approximation if no actual payment data available
        d_payment = d_sale + timedelta(days=settlement_lag)

        # Skip if payment date is beyond query range
        if d_payment > d_to:
            continue

        # Outflow: costs on sale date
        outflow = total_commission + total_delivery + total_promo

        # Inflow: net revenue on payment date (approximation)
        inflow = gross_revenue - total_refunds

        # Calculate net
        net_cashflow = inflow - outflow

        # Generate hash for idempotency
        src_data = f"{d_payment}|{marketplace}|{inflow:.2f}|{outflow:.2f}"
        src_hash = hashlib.sha256(src_data.encode()).hexdigest()

        results.append(
            {
                "d": d_payment,
                "marketplace": marketplace,
                "inflow": round(inflow, 2),
                "outflow": round(outflow, 2),
                "net": round(net_cashflow, 2),
                "src_hash": src_hash,
                "reason_code": "approximation_with_lag",  # Mark as estimate
            }
        )

    return results


def upsert_cashflow_daily(db: Session, records: list[dict]) -> int:
    """Upsert cashflow records to cashflow_daily table.

    Args:
        db: Database session
        records: List of cashflow records

    Returns:
        Number of records upserted

    """
    from sqlalchemy import Table

    from app.db.models import Base

    # Get table metadata
    metadata = Base.metadata
    cashflow_table = Table("cashflow_daily", metadata, autoload_with=db.get_bind())

    count = 0
    for rec in records:
        # Check if exists
        stmt = select(cashflow_table).where(
            cashflow_table.c.d == rec["d"], cashflow_table.c.marketplace == rec["marketplace"]
        )
        existing = db.execute(stmt).first()

        if existing:
            # Update if hash differs
            if existing.src_hash != rec["src_hash"]:
                db.execute(
                    cashflow_table.update()
                    .where(
                        cashflow_table.c.d == rec["d"],
                        cashflow_table.c.marketplace == rec["marketplace"],
                    )
                    .values(
                        inflow=rec["inflow"],
                        outflow=rec["outflow"],
                        net=rec["net"],
                        src_hash=rec["src_hash"],
                    )
                )
                count += 1
        else:
            # Insert new
            db.execute(
                cashflow_table.insert().values(
                    d=rec["d"],
                    marketplace=rec["marketplace"],
                    inflow=rec["inflow"],
                    outflow=rec["outflow"],
                    net=rec["net"],
                    src_hash=rec["src_hash"],
                )
            )
            count += 1

    db.commit()
    return count
