"""Pricing service orchestration."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import SKU, CostPriceHistory, PricingAdvice
from app.domain.pricing.elasticity import (
    build_price_demand_series,
    estimate_price_elasticity,
)
from app.domain.pricing.explain import build_pricing_explanation
from app.domain.pricing.promo_effects import measure_promo_lift
from app.domain.pricing.recommend import recommend_price_or_discount


def _settings_for_pricing() -> dict:
    """Get pricing settings as dict."""
    s = get_settings()
    return {
        "PRICING_MIN_MARGIN_PCT": s.pricing_min_margin_pct,
        "PRICING_MAX_DISCOUNT_PCT": s.pricing_max_discount_pct,
        "PRICING_MIN_PRICE_STEP": s.pricing_min_price_step,
    }


def _get_sku_info(db: Session, sku_id: int, org_id: int) -> dict:
    """Get SKU metadata including cost and pricing constraints."""
    # Get SKU basic info (scoped to org)
    stmt = select(SKU).where(SKU.id == sku_id, SKU.org_id == org_id)
    sku = db.execute(stmt).scalar_one_or_none()

    if not sku:
        return {}

    # Get latest cost price (scoped to org)
    stmt = (
        select(CostPriceHistory.cost_price)
        .where(CostPriceHistory.sku_id == sku_id, CostPriceHistory.org_id == org_id)
        .where(CostPriceHistory.dt_from <= date.today())
        .order_by(CostPriceHistory.dt_from.desc())
        .limit(1)
    )
    unit_cost = db.execute(stmt).scalar() or 0.0

    # TODO: Get commission rate and delivery cost from actual data
    # For now, use conservative estimates
    avg_commission = 0.15 * unit_cost  # 15% commission estimate
    avg_delivery = 50.0  # Flat delivery cost estimate

    # TODO: Get MAP from settings
    settings = get_settings()
    map_json = settings.pricing_map_json or "{}"
    import json

    try:
        map_dict = json.loads(map_json)
    except json.JSONDecodeError:
        map_dict = {}

    map_price = map_dict.get(sku.article, 0.0)

    return {
        "sku_id": sku_id,
        "article": sku.article or f"SKU_{sku_id}",
        "unit_cost": unit_cost,
        "avg_commission": avg_commission,
        "avg_delivery": avg_delivery,
        "map_price": map_price,
    }


def compute_pricing_for_skus(
    db: Session,
    *,
    org_id: int,
    sku_ids: list[int] | None = None,
    marketplace: str | None = None,
    window: int = 28,
) -> list[dict]:
    """Compute pricing recommendations for SKUs.

    Args:
        db: Database session
        org_id: Organization ID for scoping
        sku_ids: List of SKU IDs (None = all SKUs)
        marketplace: Filter by marketplace (WB/OZON)
        window: Promo comparison window (days)

    Returns:
        List of pricing recommendations with explanations

    """
    # Get list of SKUs to process (scoped to org)
    stmt = select(SKU.id, SKU.article).where(SKU.org_id == org_id, SKU.marketplace.isnot(None))

    if marketplace:
        stmt = stmt.where(SKU.marketplace == marketplace)

    if sku_ids:
        stmt = stmt.where(SKU.id.in_(sku_ids))

    skus = db.execute(stmt).all()

    out = []
    st = _settings_for_pricing()

    for sku_row in skus:
        sku_id = sku_row.id
        article = sku_row.article or f"SKU_{sku_id}"

        # Get SKU metadata (scoped to org)
        sku_info = _get_sku_info(db, sku_id, org_id)

        if not sku_info:
            continue

        # Build price-demand series
        series = build_price_demand_series(db, sku_id, None, days_back=176)

        if not series:
            continue

        # Estimate elasticity
        el = estimate_price_elasticity(series)

        # Measure promo lift
        promo = measure_promo_lift(series, window=min(window, 28))

        # Generate recommendation
        rec = recommend_price_or_discount(
            sku_info=sku_info,
            series=series,
            el=el,
            promo=promo,
            settings=st,
        )

        # Generate explanation and hash
        explain, rh = build_pricing_explanation(
            article,
            rec.get("current_price"),
            el.get("elasticity"),
            promo.get("lift"),
            rec.get("guardrails"),
            rec.get("expected_profit", 0),
            rec.get("action", "keep"),
        )

        rec["explain"] = explain
        rec["rationale_hash"] = rh
        rec["elasticity"] = el.get("elasticity")
        rec["promo_lift"] = promo.get("lift")

        out.append(rec)

    # Save to pricing_advice table (scoped to org)
    today = date.today()

    for rec in out:
        advice = PricingAdvice(
            d=today,
            sku_id=rec["sku_id"],
            org_id=org_id,
            suggested_price=rec.get("suggested_price"),
            suggested_discount_pct=rec.get("suggested_discount_pct"),
            expected_profit=rec.get("expected_profit"),
            quality=rec.get("quality"),
            rationale_hash=rec.get("rationale_hash"),
            reason_code=rec.get("reason_code"),
        )
        db.merge(advice)

    db.commit()

    return out
