"""Inventory management and supply recommendation logic.

Business logic for calculating:
- Rolling velocity (sales velocity over N days)
- Stock cover days
- Supply recommendations

NO DATA ACCESS - pure functions only. Data access happens in services layer.
"""

from __future__ import annotations


def rolling_velocity(qty_by_day: list[int], window: int) -> float:
    """Calculate rolling sales velocity (average daily sales over window).

    Args:
        qty_by_day: List of daily sales quantities, in chronological order
                   (most recent day last)
        window: Number of days to average over (e.g., 7, 14, 28)

    Returns:
        Average daily sales rate (units per day)

    Examples:
        >>> rolling_velocity([10, 12, 8, 15, 11, 9, 14], 7)
        11.285714285714286
        >>> rolling_velocity([10, 12, 8], 7)  # Window > data length
        10.0
        >>> rolling_velocity([], 7)
        0.0
    """
    if not qty_by_day:
        return 0.0

    n = min(window, len(qty_by_day))
    if n == 0:
        return 0.0

    # Take last N days
    recent_sales = qty_by_day[-n:]
    return sum(recent_sales) / float(n)


def stock_cover_days(on_hand: int, in_transit: int, velocity: float) -> float:
    """Calculate stock cover in days at current velocity.

    Stock Cover = (On Hand + In Transit) / Velocity

    Args:
        on_hand: Current stock on hand
        in_transit: Stock in transit (reserved, incoming)
        velocity: Daily sales velocity (units per day)

    Returns:
        Number of days until stockout at current velocity
        Returns 999.0 if velocity is 0 (infinite stock cover)

    Examples:
        >>> stock_cover_days(100, 50, 10.0)
        15.0
        >>> stock_cover_days(50, 0, 5.0)
        10.0
        >>> stock_cover_days(100, 0, 0.0)
        999.0
    """
    if velocity <= 0:
        return 999.0  # Infinite cover (no sales)

    total_stock = on_hand + in_transit
    return total_stock / velocity


def recommend_supply(
    sv: float,
    window_days: int,
    on_hand: int,
    in_transit: int,
    safety_coeff: float = 1.5,
    demand_std: float = 0.0,
) -> int:
    """Calculate recommended supply quantity using Wilson formula with safety stock.

    Recommendation = (Velocity × Window) + Safety Stock - (On Hand + In Transit)

    Safety Stock = safety_coeff × std_deviation × √window_days

    Args:
        sv: Sales velocity (average units per day)
        window_days: Planning window (14 or 28 days)
        on_hand: Current stock on hand
        in_transit: Stock in transit
        safety_coeff: Safety stock coefficient (default 1.5)
        demand_std: Standard deviation of daily demand (default 0.0)

    Returns:
        Recommended quantity to order (>= 0)

    Examples:
        >>> recommend_supply(10.0, 14, 50, 20, 1.5, 3.0)
        87  # (10*14) + (1.5*3*√14) - (50+20) ≈ 87
        >>> recommend_supply(5.0, 28, 100, 0, 1.5, 2.0)
        57  # (5*28) + (1.5*2*√28) - 100 ≈ 56
        >>> recommend_supply(10.0, 14, 200, 50, 1.5, 0.0)
        0  # Already have enough stock
    """
    # Expected demand over window
    expected_demand = sv * window_days

    # Safety stock (buffer against variability)
    safety = int(round(safety_coeff * demand_std * (window_days**0.5)))

    # Total need
    total_need = int(round(expected_demand + safety))

    # Current available
    current_available = on_hand + in_transit

    # Recommendation
    need = total_need - current_available
    return max(0, need)
