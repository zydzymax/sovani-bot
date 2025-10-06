"""Inventory and stocks API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.db.models import SKU, DailySales, DailyStock, Warehouse
from app.web.deps import CurrentUser, DBSession, OrgScope
from app.web.schemas import StockRow

router = APIRouter()


@router.get("/warehouse-turnover")
def get_warehouse_turnover(
    org_id: OrgScope,
    db: DBSession,
    user: CurrentUser,
    days: int = Query(30, ge=7, le=90, description="Period for turnover calculation"),
    marketplace: str | None = Query(None, description="Filter by marketplace (WB/OZON)"),
    min_stock: int = Query(0, ge=0, description="Minimum current stock to include"),
) -> list[dict]:
    """Get warehouse-level turnover and restocking recommendations.

    Calculates velocity (units sold per day) and days of stock remaining
    for each warehouse. Warehouses with low days remaining need restocking.

    Returns warehouses sorted by urgency (lowest days remaining first).
    """
    from datetime import date, timedelta

    from sqlalchemy import func

    today = date.today()
    period_start = today - timedelta(days=days)

    # Get sales velocity (units per day) by SKU and warehouse
    sales_query = (
        select(
            DailySales.sku_id,
            DailySales.warehouse_id,
            SKU.marketplace,
            SKU.nm_id,
            SKU.ozon_id,
            Warehouse.name.label("warehouse_name"),
            func.sum(DailySales.qty).label("total_sold"),
            func.count(func.distinct(DailySales.d)).label("sale_days"),
        )
        .join(SKU, DailySales.sku_id == SKU.id)
        .join(Warehouse, DailySales.warehouse_id == Warehouse.id)
        .where(DailySales.d >= period_start)
        .where(DailySales.d <= today)
        .group_by(
            DailySales.sku_id,
            DailySales.warehouse_id,
            SKU.marketplace,
            SKU.nm_id,
            SKU.ozon_id,
            Warehouse.name,
        )
    )

    if marketplace:
        sales_query = sales_query.where(SKU.marketplace == marketplace)

    sales_data = {
        (row.sku_id, row.warehouse_id): {
            "marketplace": row.marketplace,
            "sku_key": row.nm_id or row.ozon_id,
            "warehouse": row.warehouse_name,
            "total_sold": row.total_sold,
            "sale_days": row.sale_days,
            "velocity": row.total_sold / days if days > 0 else 0,  # units per day
        }
        for row in db.execute(sales_query).all()
    }

    # Get current stock levels
    stock_query = (
        select(
            DailyStock.sku_id,
            DailyStock.warehouse_id,
            DailyStock.on_hand,
            SKU.marketplace,
            SKU.nm_id,
            SKU.ozon_id,
            Warehouse.name.label("warehouse_name"),
        )
        .join(SKU, DailyStock.sku_id == SKU.id)
        .join(Warehouse, DailyStock.warehouse_id == Warehouse.id)
        .where(DailyStock.d == today)
        .where(DailyStock.on_hand >= min_stock)
    )

    if marketplace:
        stock_query = stock_query.where(SKU.marketplace == marketplace)

    recommendations = []
    for row in db.execute(stock_query).all():
        key = (row.sku_id, row.warehouse_id)
        sales_info = sales_data.get(key, {})

        velocity = sales_info.get("velocity", 0)
        days_remaining = (row.on_hand / velocity) if velocity > 0 else 999

        # Recommendation logic
        if days_remaining < 14:
            urgency = "high"
            action = f"Критично: осталось ~{days_remaining:.1f} дней"
        elif days_remaining < 30:
            urgency = "medium"
            action = f"Требуется пополнение: ~{days_remaining:.1f} дней"
        else:
            urgency = "low"
            action = f"Запас достаточен: ~{days_remaining:.1f} дней"

        recommendations.append(
            {
                "marketplace": row.marketplace,
                "sku_key": row.nm_id or row.ozon_id,
                "warehouse": row.warehouse_name,
                "current_stock": row.on_hand,
                "velocity_per_day": round(velocity, 2),
                "days_remaining": round(days_remaining, 1),
                "urgency": urgency,
                "recommendation": action,
                "suggested_qty": max(0, int(velocity * 30 - row.on_hand)),  # Enough for 30 days
            }
        )

    # Sort by urgency (lowest days remaining first)
    recommendations.sort(key=lambda x: x["days_remaining"])

    return recommendations


@router.get("/stocks", response_model=list[StockRow])
def get_stocks(
    org_id: OrgScope,
    db: DBSession,
    user: CurrentUser,
    stock_date: date = Query(..., alias="date", description="Date for stock snapshot (YYYY-MM-DD)"),
    sku_id: int | None = Query(None, description="Filter by SKU ID"),
    warehouse_id: int | None = Query(None, description="Filter by warehouse ID"),
    limit: int = Query(100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order by on_hand"),
) -> list[StockRow]:
    """Get inventory/stock data for specified date.

    Returns stock levels (on_hand, in_transit) per SKU/warehouse combination.
    """
    stmt = select(DailyStock).where(DailyStock.d == stock_date)

    if sku_id:
        stmt = stmt.where(DailyStock.sku_id == sku_id)
    if warehouse_id:
        stmt = stmt.where(DailyStock.warehouse_id == warehouse_id)

    # Apply ordering
    if order == "desc":
        stmt = stmt.order_by(DailyStock.on_hand.desc())
    else:
        stmt = stmt.order_by(DailyStock.on_hand.asc())

    stmt = stmt.limit(limit).offset(offset)

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
