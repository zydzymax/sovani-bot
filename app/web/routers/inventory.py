"""Inventory and stocks API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.db.models import SKU, DailyStock, Warehouse
from app.web.deps import CurrentUser, DBSession
from app.web.schemas import StockRow

router = APIRouter()


@router.get("/stocks", response_model=list[StockRow])
def get_stocks(
    db: DBSession,
    user: CurrentUser,
    stock_date: date = Query(..., alias="date", description="Date for stock snapshot (YYYY-MM-DD)"),
    sku_id: int | None = Query(None, description="Filter by SKU ID"),
    warehouse_id: int | None = Query(None, description="Filter by warehouse ID"),
    limit: int = Query(100, ge=1, le=500, description="Max rows to return"),
) -> list[StockRow]:
    """Get inventory/stock data for specified date.

    Returns stock levels (on_hand, in_transit) per SKU/warehouse combination.
    """
    stmt = select(DailyStock).where(DailyStock.d == stock_date)

    if sku_id:
        stmt = stmt.where(DailyStock.sku_id == sku_id)
    if warehouse_id:
        stmt = stmt.where(DailyStock.warehouse_id == warehouse_id)

    stmt = stmt.limit(limit)

    results = db.execute(stmt).scalars().all()

    # Enrich with SKU and warehouse data
    output = []
    for row in results:
        sku = db.get(SKU, row.sku_id)
        warehouse = db.get(Warehouse, row.warehouse_id)

        output.append(
            StockRow(
                sku_id=row.sku_id,
                sku_key=sku.nm_id or sku.ozon_id if sku else None,
                marketplace=sku.marketplace if sku else None,
                warehouse=warehouse.name if warehouse else None,
                on_hand=row.on_hand,
                in_transit=row.in_transit,
                total=row.on_hand + row.in_transit,
            )
        )

    return output
