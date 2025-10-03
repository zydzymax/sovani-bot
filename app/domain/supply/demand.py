"""Demand forecasting and sales velocity calculations for supply planning."""

from __future__ import annotations

import math
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DailySales


def rolling_sv(db: Session, sku_id: int, wh_id: int | None, org_id: int, window: int) -> float:
    """Calculate rolling sales velocity (units/day) over window.

    Args:
        db: Database session
        sku_id: SKU ID
        wh_id: Warehouse ID (None = all warehouses)
        org_id: Organization ID for scoping
        window: Number of days to look back

    Returns:
        Average units sold per day (float)

    """
    end_date = date.today()
    start_date = end_date - timedelta(days=window)

    # Query DailySales for this SKU/warehouse in window (scoped to org)
    stmt = (
        select(func.sum(DailySales.qty))
        .where(DailySales.sku_id == sku_id)
        .where(DailySales.org_id == org_id)
        .where(DailySales.d >= start_date)
        .where(DailySales.d <= end_date)
    )

    if wh_id is not None:
        stmt = stmt.where(DailySales.warehouse_id == wh_id)

    total_qty = db.execute(stmt).scalar() or 0

    # Avoid division by zero
    if window == 0:
        return 0.0

    return float(total_qty) / window


def forecast_qty(sv: float, window: int) -> int:
    """Forecast demand quantity for future window.

    Simple linear forecast: sv * window days, rounded up.

    Args:
        sv: Sales velocity (units/day)
        window: Forecast horizon (days)

    Returns:
        Forecasted quantity (integer, rounded up)

    """
    if sv <= 0:
        return 0

    forecast = sv * window
    return math.ceil(forecast)


def stock_cover_days(on_hand: int, in_transit: int, sv: float) -> float:
    """Calculate stock coverage in days.

    Days of stock = (on_hand + in_transit) / sv

    Args:
        on_hand: Current stock on hand
        in_transit: Stock in transit (not yet received)
        sv: Sales velocity (units/day)

    Returns:
        Days of coverage (float). Returns inf if sv=0.

    """
    total_stock = on_hand + in_transit

    if sv <= 0:
        # No sales velocity → infinite coverage (or zero if no stock)
        return float("inf") if total_stock > 0 else 0.0

    return total_stock / sv


def demand_stdev(db: Session, sku_id: int, wh_id: int | None, org_id: int, window: int) -> float:
    """Calculate standard deviation of daily demand over window.

    Used for safety stock calculation.

    Args:
        db: Database session
        sku_id: SKU ID
        wh_id: Warehouse ID (None = all warehouses)
        org_id: Organization ID for scoping
        window: Number of days to look back

    Returns:
        Standard deviation of daily quantities

    """
    end_date = date.today()
    start_date = end_date - timedelta(days=window)

    # Group by day and sum (in case of multiple entries per day) (scoped to org)
    stmt = (
        select(DailySales.d, func.sum(DailySales.qty).label("daily_qty"))
        .where(DailySales.sku_id == sku_id)
        .where(DailySales.org_id == org_id)
        .where(DailySales.d >= start_date)
        .where(DailySales.d <= end_date)
    )

    if wh_id is not None:
        stmt = stmt.where(DailySales.warehouse_id == wh_id)

    stmt = stmt.group_by(DailySales.d)

    results = db.execute(stmt).all()

    if not results or len(results) < 2:
        return 0.0

    # Calculate stdev
    quantities = [row.daily_qty or 0 for row in results]
    mean_qty = sum(quantities) / len(quantities)
    variance = sum((q - mean_qty) ** 2 for q in quantities) / (len(quantities) - 1)

    return math.sqrt(variance)
