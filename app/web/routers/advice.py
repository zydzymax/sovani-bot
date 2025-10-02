"""Supply advice/recommendations API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.db.models import SKU, AdviceSupply, DailyStock, MetricsDaily, Warehouse
from app.services.recalc_metrics import build_advice_explanation
from app.web.deps import CurrentUser, DBSession
from app.web.schemas import AdviceRow

router = APIRouter()


@router.get("", response_model=list[AdviceRow])
def get_advice(
    db: DBSession,
    user: CurrentUser,
    advice_date: date = Query(
        default_factory=date.today, alias="date", description="Date for advice"
    ),
    window: int | None = Query(None, description="Planning window: 14 or 28 days"),
    sku_id: int | None = Query(None, description="Filter by SKU ID"),
    warehouse_id: int | None = Query(None, description="Filter by warehouse ID"),
    limit: int = Query(100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order by recommended_qty"),
) -> list[AdviceRow]:
    """Get supply recommendations with explainability.

    Returns recommended order quantities based on sales velocity and safety stock.
    Each recommendation includes a human-readable explanation.
    """
    stmt = select(AdviceSupply).where(AdviceSupply.d == advice_date)

    if window:
        stmt = stmt.where(AdviceSupply.window_days == window)
    if sku_id:
        stmt = stmt.where(AdviceSupply.sku_id == sku_id)
    if warehouse_id:
        stmt = stmt.where(AdviceSupply.warehouse_id == warehouse_id)

    # Apply ordering
    if order == "desc":
        stmt = stmt.order_by(AdviceSupply.recommended_qty.desc())
    else:
        stmt = stmt.order_by(AdviceSupply.recommended_qty.asc())

    stmt = stmt.limit(limit).offset(offset)

    results = db.execute(stmt).scalars().all()

    # Enrich with SKU, warehouse, metrics, and generate explanation
    output = []
    for row in results:
        sku = db.get(SKU, row.sku_id)
        warehouse = db.get(Warehouse, row.warehouse_id)

        # Get metrics for SV calculation
        metrics_stmt = select(MetricsDaily).where(
            MetricsDaily.d == advice_date, MetricsDaily.sku_id == row.sku_id
        )
        metrics = db.execute(metrics_stmt).scalar_one_or_none()

        # Get stock data
        stock_stmt = select(DailyStock).where(
            DailyStock.d == advice_date,
            DailyStock.sku_id == row.sku_id,
            DailyStock.warehouse_id == row.warehouse_id,
        )
        stock = db.execute(stock_stmt).scalar_one_or_none()

        # Get sales velocity for explanation
        sv = None
        if metrics:
            sv = metrics.sv14 if row.window_days == 14 else metrics.sv28

        # Generate explanation on the fly
        explain = None
        if sv and stock:
            forecast = int(sv * row.window_days)
            safety = int(sv * (row.window_days**0.5) * 1.5)
            explain, _ = build_advice_explanation(
                marketplace=sku.marketplace or "N/A" if sku else "N/A",
                wh_name=warehouse.name or "N/A" if warehouse else "N/A",
                window_days=row.window_days,
                sv=sv,
                forecast=forecast,
                safety=safety,
                on_hand=stock.on_hand,
                in_transit=stock.in_transit,
                recommended=row.recommended_qty,
            )

        output.append(
            AdviceRow(
                sku_id=row.sku_id,
                sku_key=sku.nm_id or sku.ozon_id if sku else None,
                marketplace=sku.marketplace if sku else None,
                warehouse=warehouse.name if warehouse else None,
                window_days=row.window_days,
                recommended_qty=row.recommended_qty,
                sv=sv,
                on_hand=stock.on_hand if stock else None,
                in_transit=stock.in_transit if stock else None,
                explain=explain,
            )
        )

    return output
