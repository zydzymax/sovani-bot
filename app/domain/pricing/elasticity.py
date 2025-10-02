"""Price elasticity estimation from historical data."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DailySales, DailyStock


class PriceDemandPoint(TypedDict):
    """Single observation of price and demand."""

    d: date
    price: float
    units: int
    promo_flag: bool
    stockout: bool
    weekday: int


class ElasticityEstimate(TypedDict):
    """Price elasticity estimation result."""

    elasticity: float | None
    quality: str  # "low" | "medium"
    observations: int
    method: str


def build_price_demand_series(
    db: Session,
    sku_id: int,
    wh_id: int | None = None,
    days_back: int = 176,
) -> list[PriceDemandPoint]:
    """Build time series of price and demand observations.

    Args:
        db: Database session
        sku_id: SKU ID
        wh_id: Warehouse ID (None = aggregate all warehouses)
        days_back: Lookback window (default 176 = WB API limit)

    Returns:
        List of price-demand observations with metadata

    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    # Query DailySales with stock info
    stmt = (
        select(
            DailySales.d,
            DailySales.qty,
            DailySales.revenue_gross,
            DailyStock.on_hand,
        )
        .join(DailyStock, (DailySales.d == DailyStock.d) & (DailySales.sku_id == DailyStock.sku_id))
        .where(DailySales.sku_id == sku_id)
        .where(DailySales.d >= start_date)
        .where(DailySales.d <= end_date)
    )

    if wh_id is not None:
        stmt = stmt.where(DailySales.warehouse_id == wh_id)

    results = db.execute(stmt).all()

    series: list[PriceDemandPoint] = []

    for row in results:
        qty = row.qty or 0
        revenue = row.revenue_gross or 0.0
        on_hand = row.on_hand or 0

        # Skip if no sales
        if qty == 0:
            continue

        # Estimate price from revenue/units
        price = revenue / qty if qty > 0 else 0.0

        # Detect stockout: units=0 but on_hand was low
        stockout = (qty == 0 and on_hand < 5)

        # Simple promo detection: price drop >15% from recent average
        # (in real implementation, use promo_cost or explicit promo flag)
        promo_flag = False  # Simplified for now

        point: PriceDemandPoint = {
            "d": row.d,
            "price": price,
            "units": qty,
            "promo_flag": promo_flag,
            "stockout": stockout,
            "weekday": row.d.weekday(),
        }

        series.append(point)

    # Filter out stockouts
    series = [p for p in series if not p["stockout"]]

    # Filter outliers (price = 0 or unreasonably high)
    series = [p for p in series if 10 < p["price"] < 100000]

    return series


def estimate_price_elasticity(series: list[PriceDemandPoint]) -> ElasticityEstimate:
    """Estimate price elasticity from observations.

    Uses simple log-log regression approximation:
    ln(units) ~ ln(price) + controls

    Args:
        series: List of price-demand observations

    Returns:
        Elasticity estimate with quality indicator

    """
    if len(series) < 21:
        return {
            "elasticity": None,
            "quality": "low",
            "observations": len(series),
            "method": "insufficient_data",
        }

    # Extract log-transformed data
    valid_points = []
    for p in series:
        if p["price"] > 0 and p["units"] > 0:
            ln_price = math.log(p["price"])
            ln_units = math.log(p["units"])
            valid_points.append((ln_price, ln_units, p["weekday"]))

    if len(valid_points) < 21:
        return {
            "elasticity": None,
            "quality": "low",
            "observations": len(valid_points),
            "method": "insufficient_valid_points",
        }

    # Simple OLS approximation: cov(ln_price, ln_units) / var(ln_price)
    ln_prices = [p[0] for p in valid_points]
    ln_units = [p[1] for p in valid_points]

    mean_ln_price = sum(ln_prices) / len(ln_prices)
    mean_ln_units = sum(ln_units) / len(ln_units)

    cov = sum((p - mean_ln_price) * (u - mean_ln_units) for p, u in zip(ln_prices, ln_units)) / len(valid_points)
    var_price = sum((p - mean_ln_price) ** 2 for p in ln_prices) / len(valid_points)

    if var_price < 0.01:
        # Price doesn't vary enough
        return {
            "elasticity": None,
            "quality": "low",
            "observations": len(valid_points),
            "method": "low_price_variance",
        }

    elasticity = cov / var_price

    # Elasticity should be negative for normal goods
    # If positive, data quality is questionable
    quality = "medium" if elasticity < 0 and abs(elasticity) < 5 else "low"

    return {
        "elasticity": elasticity,
        "quality": quality,
        "observations": len(valid_points),
        "method": "log_log_ols",
    }
