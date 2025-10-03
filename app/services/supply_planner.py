"""Supply planner service facade."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.db.models import AdviceSupply
from app.domain.supply.constraints import collect_candidates
from app.domain.supply.explain import generate_explanation, generate_hash
from app.domain.supply.planner_heur import plan_heuristic


def generate_supply_plan(
    db: Session,
    *,
    org_id: int,
    window: int,
    marketplace: str | None = None,
    wh_id: int | None = None,
) -> list[dict]:
    """Generate supply plan and save to database.

    Args:
        db: Database session
        org_id: Organization ID for scoping
        window: Planning window (14 or 28 days)
        marketplace: Filter by marketplace (optional)
        wh_id: Filter by warehouse (optional)

    Returns:
        List of supply plans with explanations

    """
    # Collect candidates with constraints (scoped to org)
    candidates = collect_candidates(db, org_id, window, marketplace, wh_id)

    # Run heuristic planner
    plans = plan_heuristic(candidates)

    # Save to database and prepare response
    results = []
    today = date.today()

    for plan in plans:
        # Generate explanation and hash
        explain = generate_explanation(plan)
        rationale_hash = generate_hash(plan)

        # Upsert to AdviceSupply (scoped to org)
        advice = AdviceSupply(
            d=today,
            sku_id=plan.sku_id,
            warehouse_id=plan.wh_id,
            org_id=org_id,
            marketplace=plan.marketplace,
            recommended_qty=plan.recommended_qty,
            rationale_hash=rationale_hash,
        )

        db.merge(advice)

        # Prepare response
        results.append(
            {
                "marketplace": plan.marketplace,
                "wh_id": plan.wh_id,
                "wh_name": plan.wh_name,
                "sku_id": plan.sku_id,
                "article": plan.article,
                "window": plan.window,
                "sv": plan.sv,
                "forecast": plan.forecast,
                "safety": plan.safety,
                "on_hand": plan.on_hand,
                "in_transit": plan.in_transit,
                "recommended_qty": plan.recommended_qty,
                "unit_cost": plan.unit_cost,
                "explanation": explain,
            }
        )

    db.commit()

    return results
