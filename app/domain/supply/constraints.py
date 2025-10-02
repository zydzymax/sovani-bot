"""Constraint collection for supply planning."""

from __future__ import annotations

import json
import math
from datetime import date
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CostPriceHistory, DailyStock, SKU, Warehouse
from app.domain.supply.demand import demand_stdev, rolling_sv


class PlanningCandidate(TypedDict):
    """Supply planning candidate with all constraints."""

    marketplace: str
    wh_id: int
    wh_name: str
    sku_id: int
    article: str
    nm_id: str | None
    ozon_id: str | None
    sv: float
    window: int
    on_hand: int
    in_transit: int
    forecast: int
    safety: int
    min_batch: int
    multiplicity: int
    max_per_slot: int
    unit_cost: float


def get_current_cost(db: Session, sku_id: int, as_of: date | None = None) -> float:
    """Get current cost price for SKU.

    Args:
        db: Database session
        sku_id: SKU ID
        as_of: Date to check cost (default: today)

    Returns:
        Cost price (float). Returns 0.0 if no cost found.

    """
    if as_of is None:
        as_of = date.today()

    # Get latest cost where dt_from <= as_of
    stmt = (
        select(CostPriceHistory.cost_price)
        .where(CostPriceHistory.sku_id == sku_id)
        .where(CostPriceHistory.dt_from <= as_of)
        .order_by(CostPriceHistory.dt_from.desc())
        .limit(1)
    )

    result = db.execute(stmt).scalar()
    return result or 0.0


def get_latest_stock(db: Session, sku_id: int, wh_id: int) -> tuple[int, int]:
    """Get latest stock snapshot for SKU×warehouse.

    Args:
        db: Database session
        sku_id: SKU ID
        wh_id: Warehouse ID

    Returns:
        Tuple (on_hand, in_transit)

    """
    stmt = (
        select(DailyStock.on_hand, DailyStock.in_transit)
        .where(DailyStock.sku_id == sku_id)
        .where(DailyStock.warehouse_id == wh_id)
        .order_by(DailyStock.d.desc())
        .limit(1)
    )

    result = db.execute(stmt).first()
    if not result:
        return (0, 0)

    return (result.on_hand or 0, result.in_transit or 0)


def get_warehouse_capacity(marketplace: str, wh_name: str) -> int:
    """Get warehouse capacity limit from config.

    Args:
        marketplace: Marketplace (WB/OZON)
        wh_name: Warehouse name

    Returns:
        Capacity limit (0 = unlimited)

    """
    settings = get_settings()
    capacity_json_str = settings.warehouse_capacity_json or "{}"

    try:
        capacity_map = json.loads(capacity_json_str)
    except json.JSONDecodeError:
        capacity_map = {}

    # Try exact match: "WB:Казань"
    key = f"{marketplace}:{wh_name}"
    return capacity_map.get(key, 0)


def collect_candidates(
    db: Session,
    window: int,
    marketplace: str | None = None,
    wh_id: int | None = None,
) -> list[PlanningCandidate]:
    """Collect planning candidates with all constraints.

    Args:
        db: Database session
        window: Planning window (14 or 28 days)
        marketplace: Filter by marketplace (optional)
        wh_id: Filter by warehouse (optional)

    Returns:
        List of planning candidates with SV, forecast, safety stock, constraints

    """
    settings = get_settings()

    # Get all active SKU×Warehouse combinations from latest stock
    stmt = (
        select(
            DailyStock.sku_id,
            DailyStock.warehouse_id,
            DailyStock.on_hand,
            DailyStock.in_transit,
            SKU.marketplace,
            SKU.article,
            SKU.nm_id,
            SKU.ozon_id,
            Warehouse.name.label("wh_name"),
        )
        .join(SKU, DailyStock.sku_id == SKU.id)
        .join(Warehouse, DailyStock.warehouse_id == Warehouse.id)
        .where(DailyStock.d == date.today())  # Latest snapshot
    )

    if marketplace:
        stmt = stmt.where(SKU.marketplace == marketplace)

    if wh_id:
        stmt = stmt.where(DailyStock.warehouse_id == wh_id)

    results = db.execute(stmt).all()

    candidates: list[PlanningCandidate] = []

    for row in results:
        sku_id = row.sku_id
        warehouse_id = row.warehouse_id
        mkpl = row.marketplace
        article = row.article or f"{mkpl}_{sku_id}"
        wh_name = row.wh_name or "Unknown"

        # Calculate SV
        sv = rolling_sv(db, sku_id, warehouse_id, window)

        # Forecast = SV * window
        forecast = math.ceil(sv * window) if sv > 0 else 0

        # Safety stock = COEFF * sqrt(window) * stdev
        stdev = demand_stdev(db, sku_id, warehouse_id, window)
        safety = math.ceil(settings.planner_safety_coeff * math.sqrt(window) * stdev)

        # Get cost
        unit_cost = get_current_cost(db, sku_id)

        # Get constraints from settings
        min_batch = settings.planner_min_batch
        multiplicity = settings.planner_multiplicity
        max_per_slot = settings.planner_max_per_slot

        candidate: PlanningCandidate = {
            "marketplace": mkpl,
            "wh_id": warehouse_id,
            "wh_name": wh_name,
            "sku_id": sku_id,
            "article": article,
            "nm_id": row.nm_id,
            "ozon_id": row.ozon_id,
            "sv": sv,
            "window": window,
            "on_hand": row.on_hand or 0,
            "in_transit": row.in_transit or 0,
            "forecast": forecast,
            "safety": safety,
            "min_batch": min_batch,
            "multiplicity": multiplicity,
            "max_per_slot": max_per_slot,
            "unit_cost": unit_cost,
        }

        candidates.append(candidate)

    return candidates
