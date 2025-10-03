"""What-if scenario analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.pricing.recommend import simulate_price_change


def simulate_pricing_scenario(
    db: Session, sku_id: int, new_price: float, horizon_days: int
) -> dict:
    """Simulate pricing scenario."""
    from app.domain.pricing.elasticity import build_price_demand_series, estimate_price_elasticity

    settings = get_settings()

    # Get elasticity
    series = build_price_demand_series(db, sku_id, None, days_back=90)
    el = estimate_price_elasticity(series)

    if not series:
        return {"status": "no_data", "quality": "low"}

    # Current state
    current_price = sum(r["price"] for r in series[-7:]) / min(7, len(series))
    current_units = sum(r["units"] for r in series[-7:]) / min(7, len(series))

    # Simulate
    delta = new_price - current_price
    sim = simulate_price_change(current_units, el.get("elasticity"), current_price, delta)

    profit_change = (new_price - current_price) * sim["units_new"]

    return {
        "sku_id": sku_id,
        "current_price": round(current_price, 2),
        "new_price": new_price,
        "current_units": round(current_units, 2),
        "projected_units": round(sim["units_new"], 2),
        "profit_change": round(profit_change, 2),
        "quality": el.get("quality", "low"),
    }


def simulate_supply_scenario(db: Session, sku_id: int, add_qty: int, leadtime_days: int) -> dict:
    """Simulate supply scenario."""
    from sqlalchemy import select

    from app.db.models import MetricsDaily

    # Get velocity
    stmt = (
        select(MetricsDaily.sv14)
        .where(MetricsDaily.sku_id == sku_id)
        .order_by(MetricsDaily.d.desc())
        .limit(1)
    )
    sv = db.execute(stmt).scalar()

    if not sv:
        return {"status": "no_velocity", "quality": "low"}

    # Simple model: additional stock coverage
    added_days = add_qty / sv if sv > 0 else 0

    return {
        "sku_id": sku_id,
        "add_qty": add_qty,
        "leadtime_days": leadtime_days,
        "current_velocity": round(sv, 2),
        "added_coverage_days": round(added_days, 1),
        "quality": "medium" if sv > 0 else "low",
    }


def simulate_combo(
    db: Session, sku_id: int, new_price: float, add_qty: int, horizon_days: int, leadtime_days: int
) -> dict:
    """Combined scenario."""
    pricing = simulate_pricing_scenario(db, sku_id, new_price, horizon_days)
    supply = simulate_supply_scenario(db, sku_id, add_qty, leadtime_days)

    return {
        "pricing": pricing,
        "supply": supply,
        "combined_quality": (
            "medium"
            if pricing.get("quality") == "medium" and supply.get("quality") == "medium"
            else "low"
        ),
    }
