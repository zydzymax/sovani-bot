"""Metrics recalculation service.

Recalculates derived metrics from raw daily data:
- Revenue net, COGS, Profit, Margin
- Rolling velocity (SV7, SV14, SV28)
- Stock cover days
- Supply recommendations

Idempotent: can be run multiple times for the same date.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import (
    SKU,
    AdviceSupply,
    CostPriceHistory,
    DailySales,
    DailyStock,
    MetricsDaily,
)
from app.domain.finance.pnl import (
    calc_cogs,
    calc_margin,
    calc_profit,
    calc_revenue_net,
)
from app.domain.supply.inventory import (
    recommend_supply,
    rolling_velocity,
    stock_cover_days,
)

log = get_logger("sovani_bot.recalc_metrics")


def build_advice_explanation(
    marketplace: str,
    wh_name: str,
    window_days: int,
    sv: float,
    forecast: int,
    safety: int,
    on_hand: int,
    in_transit: int,
    recommended: int,
) -> tuple[str, str]:
    """Build human-readable explanation for supply recommendation.

    Args:
        marketplace: Marketplace name (WB, OZON)
        wh_name: Warehouse name
        window_days: Planning window (days)
        sv: Sales velocity (units/day)
        forecast: Forecasted demand
        safety: Safety stock quantity
        on_hand: Current stock on hand
        in_transit: Stock in transit
        recommended: Recommended order quantity

    Returns:
        Tuple of (explanation_text, hash)

    """
    text = (
        f"{marketplace}, {wh_name}: SV{window_days}={sv:.2f}/день, окно={window_days}, "
        f"прогноз={forecast}, safety={safety}, остаток={on_hand}, в пути={in_transit} "
        f"→ рекомендовано {recommended}."
    )
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, h


def recalc_metrics_for_date(db: Session, d: date) -> int:
    """Recalculate metrics for given date.

    Args:
        db: Database session
        d: Date to recalculate (UTC)

    Returns:
        Number of SKUs processed

    """
    settings = get_settings()

    log.info("metrics_recalc_started", extra={"date": str(d)})

    # Get all SKUs with sales on this date
    stmt = select(DailySales.sku_id).where(DailySales.d == d).distinct()
    sku_ids = [row[0] for row in db.execute(stmt).all()]

    processed = 0

    for sku_id in sku_ids:
        # Get sales data for this SKU on this date
        sales_stmt = select(DailySales).where(DailySales.d == d, DailySales.sku_id == sku_id)
        sales_rows = db.execute(sales_stmt).scalars().all()

        # Aggregate across warehouses
        total_qty = sum(row.qty for row in sales_rows)
        total_revenue_gross = sum(row.revenue_gross for row in sales_rows)
        total_refunds_amount = sum(row.refunds_amount for row in sales_rows)
        total_promo = sum(row.promo_cost for row in sales_rows)
        total_delivery = sum(row.delivery_cost for row in sales_rows)
        total_commission = sum(row.commission_amount for row in sales_rows)

        # Calculate revenue net
        revenue_net = calc_revenue_net(
            total_revenue_gross,
            total_refunds_amount,
            total_promo,
            total_delivery,
            total_commission,
        )

        # Get cost history for COGS calculation
        cost_stmt = (
            select(CostPriceHistory.dt_from, CostPriceHistory.cost_price)
            .where(CostPriceHistory.sku_id == sku_id)
            .order_by(CostPriceHistory.dt_from)
        )
        cost_history = [(row[0], row[1]) for row in db.execute(cost_stmt).all()]

        # Calculate COGS
        cogs = calc_cogs(total_qty, d, sku_id, cost_history)

        # Calculate profit and margin
        profit = calc_profit(revenue_net, cogs)
        margin = calc_margin(profit, revenue_net)

        # Calculate rolling velocities (SV7, SV14, SV28)
        # Get sales history for last 28 days
        d_start = d - timedelta(days=27)  # 28 days total including today
        hist_stmt = (
            select(DailySales.d, DailySales.qty)
            .where(
                DailySales.sku_id == sku_id,
                DailySales.d >= d_start,
                DailySales.d <= d,
            )
            .order_by(DailySales.d)
        )
        sales_history = db.execute(hist_stmt).all()

        # Build daily qty array (fill missing days with 0)
        qty_by_day = []
        current_d = d_start
        hist_dict = {row[0]: row[1] for row in sales_history}

        while current_d <= d:
            qty_by_day.append(hist_dict.get(current_d, 0))
            current_d += timedelta(days=1)

        sv7 = rolling_velocity(qty_by_day, 7)
        sv14 = rolling_velocity(qty_by_day, 14)
        sv28 = rolling_velocity(qty_by_day, 28)

        # Calculate stock cover (simplified - aggregate across warehouses)
        stock_stmt = select(DailyStock.on_hand, DailyStock.in_transit).where(
            DailyStock.sku_id == sku_id, DailyStock.d == d
        )
        stock_rows = db.execute(stock_stmt).all()

        total_on_hand = sum(row[0] for row in stock_rows)
        total_in_transit = sum(row[1] for row in stock_rows)
        stock_cover = stock_cover_days(total_on_hand, total_in_transit, sv14)

        # Upsert metrics
        metrics_stmt = insert(MetricsDaily).values(
            d=d,
            sku_id=sku_id,
            revenue_net=revenue_net,
            cogs=cogs,
            profit=profit,
            margin=margin,
            sv7=sv7,
            sv14=sv14,
            sv28=sv28,
            stock_cover_days=stock_cover,
        )

        if db.bind.dialect.name == "postgresql":
            metrics_stmt = metrics_stmt.on_conflict_do_update(
                index_elements=["d", "sku_id"],
                set_=dict(
                    revenue_net=metrics_stmt.excluded.revenue_net,
                    cogs=metrics_stmt.excluded.cogs,
                    profit=metrics_stmt.excluded.profit,
                    margin=metrics_stmt.excluded.margin,
                    sv7=metrics_stmt.excluded.sv7,
                    sv14=metrics_stmt.excluded.sv14,
                    sv28=metrics_stmt.excluded.sv28,
                    stock_cover_days=metrics_stmt.excluded.stock_cover_days,
                ),
            )
        else:
            metrics_stmt = metrics_stmt.on_conflict_do_update(
                index_elements=["d", "sku_id"],
                set_=dict(
                    revenue_net=metrics_stmt.excluded.revenue_net,
                    cogs=metrics_stmt.excluded.cogs,
                    profit=metrics_stmt.excluded.profit,
                    margin=metrics_stmt.excluded.margin,
                    sv7=metrics_stmt.excluded.sv7,
                    sv14=metrics_stmt.excluded.sv14,
                    sv28=metrics_stmt.excluded.sv28,
                    stock_cover_days=metrics_stmt.excluded.stock_cover_days,
                ),
            )

        db.execute(metrics_stmt)
        processed += 1

    db.commit()

    log.info("metrics_recalc_completed", extra={"date": str(d), "sku_count": processed})

    return processed


def generate_supply_advice(db: Session, d: date) -> int:
    """Generate supply recommendations with explainability.

    Args:
        db: Database session
        d: Date for recommendations (UTC)

    Returns:
        Number of advice records generated

    """
    settings = get_settings()
    log.info("supply_advice_started", extra={"date": str(d)})

    # Get all SKU/warehouse combinations with stock data
    stmt = (
        select(
            DailyStock.sku_id, DailyStock.warehouse_id, DailyStock.on_hand, DailyStock.in_transit
        )
        .where(DailyStock.d == d)
        .distinct()
    )
    stock_rows = db.execute(stmt).all()

    advice_count = 0

    for sku_id, warehouse_id, on_hand, in_transit in stock_rows:
        # Get SKU and warehouse info for explainability
        sku = db.get(SKU, sku_id)
        from app.db.models import Warehouse

        warehouse = db.get(Warehouse, warehouse_id)

        if not sku or not warehouse:
            continue

        # Get metrics for this SKU
        metrics_stmt = select(MetricsDaily).where(
            MetricsDaily.d == d, MetricsDaily.sku_id == sku_id
        )
        metrics = db.execute(metrics_stmt).scalar()

        if not metrics:
            continue

        # Generate advice for both 14 and 28 day windows
        for window_days in [14, 28]:
            sv = metrics.sv14 if window_days == 14 else metrics.sv28

            if sv <= 0:
                continue  # No sales velocity, no recommendation

            # Calculate recommendation
            forecast = int(sv * window_days)
            safety = int(sv * (window_days**0.5) * 1.5)  # 1.5 safety coefficient
            recommended = recommend_supply(sv, window_days, on_hand, in_transit, safety_coeff=1.5)

            # Build explanation with rationale
            explain_text, rationale_hash = build_advice_explanation(
                marketplace=sku.marketplace or "N/A",
                wh_name=warehouse.name or "N/A",
                window_days=window_days,
                sv=sv,
                forecast=forecast,
                safety=safety,
                on_hand=on_hand,
                in_transit=in_transit,
                recommended=recommended,
            )

            # Upsert advice with rationale_hash
            advice_stmt = insert(AdviceSupply).values(
                d=d,
                sku_id=sku_id,
                warehouse_id=warehouse_id,
                window_days=window_days,
                recommended_qty=recommended,
                rationale_hash=rationale_hash,
            )

            if db.bind.dialect.name == "postgresql":
                advice_stmt = advice_stmt.on_conflict_do_update(
                    index_elements=["d", "sku_id", "warehouse_id", "window_days"],
                    set_=dict(
                        recommended_qty=advice_stmt.excluded.recommended_qty,
                        rationale_hash=advice_stmt.excluded.rationale_hash,
                    ),
                )
            else:
                advice_stmt = advice_stmt.on_conflict_do_update(
                    index_elements=["d", "sku_id", "warehouse_id", "window_days"],
                    set_=dict(
                        recommended_qty=advice_stmt.excluded.recommended_qty,
                        rationale_hash=advice_stmt.excluded.rationale_hash,
                    ),
                )

            db.execute(advice_stmt)
            advice_count += 1

            # Log explanation for debugging
            log.debug("supply_advice_generated", extra={"explanation": explain_text})

    db.commit()
    log.info("supply_advice_completed", extra={"date": str(d), "advice_count": advice_count})

    return advice_count
