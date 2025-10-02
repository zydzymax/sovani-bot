"""P&L (Profit & Loss) calculation logic.

Business logic for calculating:
- Revenue (net)
- COGS (Cost of Goods Sold)
- Profit
- Margin

NO DATA ACCESS - pure functions only. Data access happens in services layer.
"""

from __future__ import annotations

from datetime import date


def calc_revenue_net(
    revenue_gross: float,
    refunds_amount: float,
    promo_cost: float,
    delivery_cost: float,
    commission_amount: float,
) -> float:
    """Calculate net revenue.

    Net Revenue = Gross Revenue - Refunds - Promo - Delivery - Commission

    Args:
        revenue_gross: Gross revenue from API
        refunds_amount: Total refund amount
        promo_cost: Promotion/discount costs
        delivery_cost: Delivery/logistics costs
        commission_amount: Marketplace commission

    Returns:
        Net revenue (can be negative if costs exceed gross revenue)

    """
    return revenue_gross - refunds_amount - promo_cost - delivery_cost - commission_amount


def calc_cogs(qty: int, d: date, sku_id: int, cost_history: list[tuple[date, float]]) -> float:
    """Calculate COGS (Cost of Goods Sold) for given quantity and date.

    Args:
        qty: Quantity sold
        d: Date of sale
        sku_id: SKU ID (not used in calculation, but useful for validation)
        cost_history: List of (dt_from, cost_price) tuples, sorted by dt_from ASC

    Returns:
        COGS = quantity * applicable_cost_price

    Notes:
        - Finds the latest cost price where dt_from <= d
        - If no cost price found, returns 0.0 (should be logged as warning)

    """
    if qty <= 0:
        return 0.0

    # Find applicable cost price (latest where dt_from <= d)
    applicable_cost = 0.0
    for dt_from, cost_price in sorted(cost_history, key=lambda x: x[0]):
        if dt_from <= d:
            applicable_cost = cost_price
        else:
            break

    return applicable_cost * qty


def calc_profit(revenue_net: float, cogs: float, marketing: float = 0.0) -> float:
    """Calculate profit.

    Profit = Net Revenue - COGS - Marketing

    Args:
        revenue_net: Net revenue (after all deductions)
        cogs: Cost of goods sold
        marketing: Marketing/advertising costs (default 0.0)

    Returns:
        Profit (can be negative)

    """
    return revenue_net - cogs - marketing


def calc_margin(profit: float, revenue_net: float) -> float:
    """Calculate profit margin percentage.

    Margin % = (Profit / Net Revenue) * 100

    Args:
        profit: Profit amount
        revenue_net: Net revenue

    Returns:
        Margin percentage (0.0 if revenue_net is 0 or negative)

    """
    if revenue_net <= 0:
        return 0.0

    return (profit / revenue_net) * 100.0
