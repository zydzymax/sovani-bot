"""Pricing & promo analytics API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limits import check_rate_limit
from app.db.models import SKU, PricingAdvice
from app.db.session import get_db
from app.services.pricing_service import compute_pricing_for_skus
from app.web.deps import OrgScope, require_admin

router = APIRouter(prefix="/api/v1/pricing", tags=["pricing"])

DBSession = Annotated[Session, Depends(get_db)]


@router.get("/advice")
async def get_pricing_advice(
    org_id: OrgScope,
    db: DBSession,
    marketplace: str | None = Query(None),
    sku_id: int | None = Query(None),
    quality: str | None = Query(None, description="Filter by quality: low | medium"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    """Get pricing recommendations.

    Returns list of pricing advice with filters.
    """
    stmt = (
        select(
            PricingAdvice.d,
            PricingAdvice.sku_id,
            PricingAdvice.suggested_price,
            PricingAdvice.suggested_discount_pct,
            PricingAdvice.expected_profit,
            PricingAdvice.quality,
            PricingAdvice.rationale_hash,
            PricingAdvice.reason_code,
            SKU.article,
            SKU.marketplace,
        )
        .join(SKU, PricingAdvice.sku_id == SKU.id)
        .where(PricingAdvice.org_id == org_id)
        .order_by(PricingAdvice.expected_profit.desc().nulls_last())
    )

    if sku_id:
        stmt = stmt.where(PricingAdvice.sku_id == sku_id)

    if marketplace:
        stmt = stmt.where(SKU.marketplace == marketplace)

    if quality:
        stmt = stmt.where(PricingAdvice.quality == quality)

    stmt = stmt.offset(offset).limit(limit)

    results = db.execute(stmt).all()

    return [
        {
            "d": str(r.d),
            "sku_id": r.sku_id,
            "article": r.article,
            "marketplace": r.marketplace,
            "suggested_price": r.suggested_price,
            "suggested_discount_pct": r.suggested_discount_pct,
            "expected_profit": r.expected_profit,
            "quality": r.quality,
            "rationale_hash": r.rationale_hash,
            "reason_code": r.reason_code,
        }
        for r in results
    ]


@router.post("/compute")
async def compute_pricing(
    org_id: OrgScope,
    db: DBSession,
    _admin: Annotated[dict, Depends(require_admin)],
    marketplace: str | None = Query(None),
    sku_id: int | None = Query(None),
    window: int = Query(28, ge=7, le=28),
):
    """Recompute pricing recommendations (admin-only).

    Runs pricing analysis and saves to database.
    Rate limited per-org.
    """
    settings = get_settings()

    # Rate limit: pricing computation is expensive
    check_rate_limit(db, org_id, "pricing_compute", settings.org_rate_limit_rps)

    sku_ids = [sku_id] if sku_id else None
    res = compute_pricing_for_skus(
        db, org_id=org_id, sku_ids=sku_ids, marketplace=marketplace, window=window
    )

    return {
        "status": "success",
        "recommendations_generated": len(res),
        "window": window,
        "marketplace": marketplace,
    }
