"""Explainability for supply planning decisions."""

from __future__ import annotations

import hashlib

from app.domain.supply.planner_heur import SupplyPlan


def generate_explanation(plan: SupplyPlan) -> str:
    """Generate human-readable explanation for supply plan.

    Args:
        plan: Supply plan with recommendation

    Returns:
        Explanation string

    """
    sv_display = f"SV{plan.window}={plan.sv:.1f}/день"
    forecast_display = f"прогноз={plan.forecast}"
    safety_display = f"safety={plan.safety}"
    stock_display = f"остаток={plan.on_hand}"
    transit_display = f"в пути={plan.in_transit}"
    rec_display = f"рекомендовано {plan.recommended_qty}"

    explain = (
        f"{plan.marketplace}, {plan.wh_name}: {sv_display}, {forecast_display}, "
        f"{safety_display}, {stock_display}, {transit_display} → {rec_display}"
    )

    return explain


def generate_hash(plan: SupplyPlan) -> str:
    """Generate deterministic hash for plan rationale.

    Hash based on: marketplace, wh_id, sku_id, window, sv, forecast, safety, recommended_qty

    Args:
        plan: Supply plan

    Returns:
        SHA256 hex digest

    """
    rationale_str = (
        f"{plan.marketplace}|{plan.wh_id}|{plan.sku_id}|{plan.window}|"
        f"{plan.sv:.2f}|{plan.forecast}|{plan.safety}|{plan.recommended_qty}"
    )

    return hashlib.sha256(rationale_str.encode()).hexdigest()
