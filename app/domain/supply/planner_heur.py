"""Heuristic supply planner with constraints."""

from __future__ import annotations

import math

from app.core.config import get_settings
from app.domain.supply.constraints import PlanningCandidate
from app.domain.supply.demand import stock_cover_days


class SupplyPlan:
    """Supply plan recommendation."""

    def __init__(
        self,
        marketplace: str,
        wh_id: int,
        wh_name: str,
        sku_id: int,
        article: str,
        window: int,
        recommended_qty: int,
        sv: float,
        forecast: int,
        safety: int,
        on_hand: int,
        in_transit: int,
        unit_cost: float,
    ):
        """Initialize supply plan."""
        self.marketplace = marketplace
        self.wh_id = wh_id
        self.wh_name = wh_name
        self.sku_id = sku_id
        self.article = article
        self.window = window
        self.recommended_qty = recommended_qty
        self.sv = sv
        self.forecast = forecast
        self.safety = safety
        self.on_hand = on_hand
        self.in_transit = in_transit
        self.unit_cost = unit_cost


def ceil_to_multiplicity(qty: int, mult: int) -> int:
    """Round quantity up to nearest multiple."""
    if mult <= 1:
        return qty
    return math.ceil(qty / mult) * mult


def plan_heuristic(candidates: list[PlanningCandidate]) -> list[SupplyPlan]:
    """Heuristic supply planner.

    Algorithm:
    1. Calculate need = forecast + safety - (on_hand + in_transit)
    2. If need > 0, round to min_batch and multiplicity
    3. Sort by urgency (stock_cover_days ASC, then sv DESC)
    4. Allocate while respecting capacity and budget limits

    Args:
        candidates: List of planning candidates

    Returns:
        List of supply plans with recommendations

    """
    settings = get_settings()
    budget_limit = settings.cashflow_limit
    budget_used = 0.0

    # Sort candidates by urgency (lowest coverage first, then highest SV)
    def priority_key(c: PlanningCandidate) -> tuple[float, float]:
        cover = stock_cover_days(c["on_hand"], c["in_transit"], c["sv"])
        return (cover, -c["sv"])  # Lower cover = higher priority, higher SV = higher priority

    sorted_candidates = sorted(candidates, key=priority_key)

    plans: list[SupplyPlan] = []

    for cand in sorted_candidates:
        # Calculate need
        total_demand = cand["forecast"] + cand["safety"]
        current_stock = cand["on_hand"] + cand["in_transit"]
        need = max(0, total_demand - current_stock)

        if need == 0:
            # No replenishment needed
            continue

        # Apply min_batch
        need = max(need, cand["min_batch"])

        # Round to multiplicity
        need = ceil_to_multiplicity(need, cand["multiplicity"])

        # Apply max_per_slot
        qty_to_order = min(need, cand["max_per_slot"])

        # Check budget constraint
        cost = qty_to_order * cand["unit_cost"]
        if budget_limit > 0 and budget_used + cost > budget_limit:
            # Reduce quantity to fit budget
            affordable_qty = (
                int((budget_limit - budget_used) / cand["unit_cost"])
                if cand["unit_cost"] > 0
                else 0
            )
            qty_to_order = min(qty_to_order, affordable_qty)

            # Round down to multiplicity
            if cand["multiplicity"] > 1:
                qty_to_order = (qty_to_order // cand["multiplicity"]) * cand["multiplicity"]

            # Check min_batch
            if qty_to_order < cand["min_batch"]:
                qty_to_order = 0  # Can't afford minimum batch

        if qty_to_order > 0:
            # Create plan
            plan = SupplyPlan(
                marketplace=cand["marketplace"],
                wh_id=cand["wh_id"],
                wh_name=cand["wh_name"],
                sku_id=cand["sku_id"],
                article=cand["article"],
                window=cand["window"],
                recommended_qty=qty_to_order,
                sv=cand["sv"],
                forecast=cand["forecast"],
                safety=cand["safety"],
                on_hand=cand["on_hand"],
                in_transit=cand["in_transit"],
                unit_cost=cand["unit_cost"],
            )

            plans.append(plan)

            # Update budget
            if budget_limit > 0:
                budget_used += qty_to_order * cand["unit_cost"]

    return plans
