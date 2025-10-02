"""Supply planning API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AdviceSupply, SKU, Warehouse
from app.db.session import get_db
from app.services.supply_planner import generate_supply_plan
from app.web.deps import require_admin

router = APIRouter(prefix="/api/v1/supply", tags=["supply"])

DBSession = Annotated[Session, Depends(get_db)]


@router.get("/plan")
async def get_supply_plan(
    db: DBSession,
    window: int = Query(14, description="Planning window (14 or 28 days)"),
    marketplace: str | None = Query(None, description="Filter by marketplace"),
    warehouse_id: int | None = Query(None, description="Filter by warehouse ID"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    """Get current supply plan from database.

    Returns list of supply recommendations with explanations.
    """
    # Query AdviceSupply with joins
    stmt = (
        select(
            AdviceSupply.sku_id,
            AdviceSupply.warehouse_id,
            AdviceSupply.marketplace,
            AdviceSupply.recommended_qty,
            AdviceSupply.rationale_hash,
            SKU.article,
            SKU.nm_id,
            SKU.ozon_id,
            Warehouse.name.label("wh_name"),
        )
        .join(SKU, AdviceSupply.sku_id == SKU.id)
        .join(Warehouse, AdviceSupply.warehouse_id == Warehouse.id)
        .where(AdviceSupply.d == db.execute(select(AdviceSupply.d).order_by(AdviceSupply.d.desc()).limit(1)).scalar())
    )

    if marketplace:
        stmt = stmt.where(AdviceSupply.marketplace == marketplace)

    if warehouse_id:
        stmt = stmt.where(AdviceSupply.warehouse_id == warehouse_id)

    stmt = stmt.offset(offset).limit(limit)

    results = db.execute(stmt).all()

    return [
        {
            "sku_id": r.sku_id,
            "article": r.article,
            "nm_id": r.nm_id,
            "ozon_id": r.ozon_id,
            "marketplace": r.marketplace,
            "warehouse_id": r.warehouse_id,
            "warehouse_name": r.wh_name,
            "recommended_qty": r.recommended_qty,
            "rationale_hash": r.rationale_hash,
        }
        for r in results
    ]


@router.post("/compute")
async def compute_supply_plan(
    db: DBSession,
    _admin: Annotated[dict, Depends(require_admin)],
    window: int = Query(14, description="Planning window (14 or 28 days)"),
    marketplace: str | None = Query(None, description="Filter by marketplace"),
    warehouse_id: int | None = Query(None, description="Filter by warehouse ID"),
):
    """Recompute supply plan (admin-only).

    Runs planner and saves recommendations to database.
    """
    # Validate window
    if window not in {14, 28}:
        return {"error": "Window must be 14 or 28 days"}, 400

    # Generate plan
    plans = generate_supply_plan(db, window, marketplace, warehouse_id)

    return {
        "status": "success",
        "plans_generated": len(plans),
        "window": window,
        "marketplace": marketplace,
        "warehouse_id": warehouse_id,
    }
