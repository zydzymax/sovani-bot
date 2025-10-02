"""Dashboard API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import func, select, text

from app.db.models import SKU, DailySales, MetricsDaily
from app.web.deps import CurrentUser, DBSession
from app.web.schemas import DashboardSummary, SkuMetric

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: DBSession,
    user: CurrentUser,
    date_from: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(..., description="End date (YYYY-MM-DD)"),
) -> DashboardSummary:
    """Get dashboard summary metrics for date range.

    Returns aggregated revenue, profit, margin, units sold, and refunds.
    """
    # Use raw SQL for performance
    query = text(
        """
        SELECT
            COALESCE(SUM(revenue_gross - refunds_amount - promo_cost - delivery_cost - commission_amount), 0) AS revenue_net,
            COALESCE(SUM(qty), 0) AS units,
            COALESCE(SUM(refunds_qty), 0) AS refunds_qty
        FROM daily_sales
        WHERE d BETWEEN :d1 AND :d2
        """
    )
    result = db.execute(query, {"d1": date_from, "d2": date_to}).one()

    # Get profit and margin from metrics (if available)
    metrics_query = text(
        """
        SELECT
            COALESCE(SUM(profit), 0) AS profit,
            COALESCE(AVG(margin), 0) AS margin
        FROM metrics_daily
        WHERE d BETWEEN :d1 AND :d2
        """
    )
    metrics_result = db.execute(metrics_query, {"d1": date_from, "d2": date_to}).one()

    return DashboardSummary(
        revenue_net=float(result.revenue_net),
        profit=float(metrics_result.profit),
        margin=float(metrics_result.margin),
        units=int(result.units),
        refunds_qty=int(result.refunds_qty),
    )


@router.get("/top-sku", response_model=list[SkuMetric])
def get_top_sku(
    db: DBSession,
    user: CurrentUser,
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    metric: str = Query(
        "revenue", pattern="^(revenue|profit|units)$", description="Metric: revenue|profit|units"
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
) -> list[SkuMetric]:
    """Get top SKUs by specified metric.

    Available metrics:
    - revenue: Total revenue (gross)
    - profit: Total profit
    - units: Total units sold
    """
    # Determine order direction
    order_func = func.sum

    if metric == "revenue":
        # Revenue from daily_sales
        metric_col = func.sum(DailySales.revenue_gross)
        stmt = (
            select(
                DailySales.sku_id,
                metric_col.label("metric_value"),
                func.sum(DailySales.qty).label("units"),
            )
            .where(DailySales.d.between(date_from, date_to))
            .group_by(DailySales.sku_id)
            .order_by(metric_col.desc() if order == "desc" else metric_col.asc())
            .limit(limit)
            .offset(offset)
        )
    elif metric == "profit":
        # Profit from metrics_daily
        metric_col = func.sum(MetricsDaily.profit)
        stmt = (
            select(
                MetricsDaily.sku_id,
                metric_col.label("metric_value"),
                func.count().label("units"),  # Placeholder
            )
            .where(MetricsDaily.d.between(date_from, date_to))
            .group_by(MetricsDaily.sku_id)
            .order_by(metric_col.desc() if order == "desc" else metric_col.asc())
            .limit(limit)
            .offset(offset)
        )
    else:  # units
        metric_col = func.sum(DailySales.qty)
        stmt = (
            select(
                DailySales.sku_id,
                metric_col.label("metric_value"),
                metric_col.label("units"),
            )
            .where(DailySales.d.between(date_from, date_to))
            .group_by(DailySales.sku_id)
            .order_by(metric_col.desc() if order == "desc" else metric_col.asc())
            .limit(limit)
            .offset(offset)
        )

    results = db.execute(stmt).all()

    # Enrich with SKU data
    output = []
    for row in results:
        sku = db.get(SKU, row.sku_id)
        output.append(
            SkuMetric(
                sku_id=row.sku_id,
                sku_key=sku.nm_id or sku.ozon_id if sku else None,
                article=sku.article if sku else None,
                marketplace=sku.marketplace if sku else None,
                metric_value=float(row.metric_value),
                units=int(row.units) if row.units else None,
            )
        )

    return output
