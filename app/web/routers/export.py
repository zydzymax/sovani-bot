"""Export endpoints for CSV/XLSX downloads."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.core.limits import check_export_limit
from app.db.models import SKU, AdviceSupply, DailyStock, MetricsDaily, Warehouse
from app.db.utils import exec_scoped
from app.web.deps import CurrentUser, DBSession, OrgScope
from app.web.utils import to_csv, to_xlsx

router = APIRouter()


@router.get("/dashboard.csv")
def export_dashboard_csv(
    org_id: OrgScope,
    db: DBSession,
    user: CurrentUser,
    date_from: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date (YYYY-MM-DD)"),
    limit: int = Query(5000, le=100000),
) -> Response:
    """Export dashboard summary as CSV.

    Returns daily breakdown of revenue, profit, units, refunds.
    """
    check_export_limit(db, org_id, limit)

    # Query daily metrics (scoped to org)
    query = """
        SELECT
            d AS date,
            COALESCE(SUM(revenue_gross - refunds_amount - promo_cost - delivery_cost - commission_amount), 0) AS revenue_net,
            COALESCE(SUM(qty), 0) AS units,
            COALESCE(SUM(refunds_qty), 0) AS refunds_qty
        FROM daily_sales
        WHERE org_id = :org_id AND d BETWEEN :d1 AND :d2
        GROUP BY d
        ORDER BY d DESC
        LIMIT :lim
    """
    result = exec_scoped(db, query, {"d1": date_from, "d2": date_to, "lim": limit}, org_id).all()

    # Convert to list of dicts
    data = [
        {
            "date": row.date,
            "revenue_net": float(row.revenue_net),
            "units": int(row.units),
            "refunds_qty": int(row.refunds_qty),
        }
        for row in result
    ]

    columns = ["date", "revenue_net", "units", "refunds_qty"]
    csv_content = to_csv(data, columns)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="dashboard.csv"'},
    )


@router.get("/advice.xlsx")
def export_advice_xlsx(
    org_id: OrgScope,
    db: DBSession,
    user: CurrentUser,
    advice_date: date = Query(
        default_factory=date.today, alias="date", description="Date for advice"
    ),
    window: int | None = Query(None, description="Planning window: 14 or 28 days"),
    sku_id: int | None = Query(None, description="Filter by SKU ID"),
    warehouse_id: int | None = Query(None, description="Filter by warehouse ID"),
    limit: int = Query(5000, le=100000),
) -> Response:
    """Export supply advice as XLSX.

    Returns recommended order quantities with metrics.
    """
    check_export_limit(db, org_id, limit)

    stmt = select(AdviceSupply).where(AdviceSupply.d == advice_date, AdviceSupply.org_id == org_id)

    if window:
        stmt = stmt.where(AdviceSupply.window_days == window)
    if sku_id:
        stmt = stmt.where(AdviceSupply.sku_id == sku_id)
    if warehouse_id:
        stmt = stmt.where(AdviceSupply.warehouse_id == warehouse_id)

    stmt = stmt.order_by(AdviceSupply.recommended_qty.desc()).limit(limit)

    results = db.execute(stmt).scalars().all()

    # Enrich with SKU, warehouse, metrics (scoped to org)
    data = []
    for row in results:
        sku = db.execute(
            select(SKU).where(SKU.id == row.sku_id, SKU.org_id == org_id)
        ).scalar_one_or_none()
        warehouse = db.execute(
            select(Warehouse).where(Warehouse.id == row.warehouse_id, Warehouse.org_id == org_id)
        ).scalar_one_or_none()

        # Get metrics (scoped to org)
        metrics_stmt = select(MetricsDaily).where(
            MetricsDaily.d == advice_date,
            MetricsDaily.sku_id == row.sku_id,
            MetricsDaily.org_id == org_id,
        )
        metrics = db.execute(metrics_stmt).scalar_one_or_none()

        # Get stock (scoped to org)
        stock_stmt = select(DailyStock).where(
            DailyStock.d == advice_date,
            DailyStock.sku_id == row.sku_id,
            DailyStock.warehouse_id == row.warehouse_id,
            DailyStock.org_id == org_id,
        )
        stock = db.execute(stock_stmt).scalar_one_or_none()

        sv = None
        if metrics:
            sv = metrics.sv14 if row.window_days == 14 else metrics.sv28

        data.append(
            {
                "sku_id": row.sku_id,
                "sku_key": sku.nm_id or sku.ozon_id if sku else None,
                "marketplace": sku.marketplace if sku else None,
                "warehouse": warehouse.name if warehouse else None,
                "window_days": row.window_days,
                "sv": sv,
                "on_hand": stock.on_hand if stock else None,
                "in_transit": stock.in_transit if stock else None,
                "recommended_qty": row.recommended_qty,
            }
        )

    columns = [
        "sku_id",
        "sku_key",
        "marketplace",
        "warehouse",
        "window_days",
        "sv",
        "on_hand",
        "in_transit",
        "recommended_qty",
    ]
    xlsx_content = to_xlsx(data, columns, sheet_name="Supply Advice")

    return Response(
        content=xlsx_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="advice.xlsx"'},
    )


@router.get("/reviews.csv")
def export_reviews_csv(
    org_id: OrgScope,
    db: DBSession,
    user: CurrentUser,
    status: str | None = Query(None, description="Filter by reply_status: pending|sent"),
    marketplace: str | None = Query(
        None, pattern="^(WB|OZON)$", description="Filter by marketplace"
    ),
    limit: int = Query(5000, le=100000),
) -> Response:
    """Export reviews as CSV.

    Returns reviews with rating, text, reply status.
    """
    from app.db.models import Review

    check_export_limit(db, org_id, limit)

    stmt = select(Review).where(Review.org_id == org_id).order_by(Review.created_at_utc.desc())

    if status == "pending":
        stmt = stmt.where(Review.reply_status.is_(None))
    elif status == "sent":
        stmt = stmt.where(Review.reply_status == "sent")

    if marketplace:
        stmt = stmt.where(Review.marketplace == marketplace)

    stmt = stmt.limit(limit)
    results = db.execute(stmt).scalars().all()

    data = [
        {
            "review_id": r.review_id,
            "marketplace": r.marketplace,
            "sku_key": r.sku_key,
            "rating": r.rating,
            "text": r.text,
            "created_at": r.created_at_utc.isoformat() if r.created_at_utc else None,
            "reply_status": r.reply_status,
            "reply_text": r.reply_text,
        }
        for r in results
    ]

    columns = [
        "review_id",
        "marketplace",
        "sku_key",
        "rating",
        "text",
        "created_at",
        "reply_status",
        "reply_text",
    ]
    csv_content = to_csv(data, columns)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="reviews.csv"'},
    )
