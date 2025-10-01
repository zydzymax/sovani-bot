"""Tests for domain logic (finance and inventory calculations)."""

from datetime import date

import pytest

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


# =============================================================================
# Finance/PnL Tests
# =============================================================================


def test_calc_revenue_net():
    """Test net revenue calculation."""
    result = calc_revenue_net(
        revenue_gross=10000.0,
        refunds_amount=1000.0,
        promo_cost=500.0,
        delivery_cost=200.0,
        commission_amount=1500.0,
    )
    # 10000 - 1000 - 500 - 200 - 1500 = 6800
    assert result == 6800.0


def test_calc_revenue_net_negative():
    """Test net revenue can be negative if costs exceed revenue."""
    result = calc_revenue_net(
        revenue_gross=1000.0,
        refunds_amount=500.0,
        promo_cost=300.0,
        delivery_cost=200.0,
        commission_amount=500.0,
    )
    # 1000 - 500 - 300 - 200 - 500 = -500
    assert result == -500.0


def test_calc_cogs_simple():
    """Test COGS calculation with single cost price."""
    cost_history = [(date(2025, 1, 1), 100.0)]
    result = calc_cogs(qty=10, d=date(2025, 1, 15), sku_id=1, cost_history=cost_history)
    assert result == 1000.0  # 10 * 100


def test_calc_cogs_multiple_prices():
    """Test COGS uses correct price from history."""
    cost_history = [
        (date(2025, 1, 1), 100.0),
        (date(2025, 2, 1), 110.0),
        (date(2025, 3, 1), 120.0),
    ]

    # Sale on 2025-01-15 uses first price
    result1 = calc_cogs(qty=10, d=date(2025, 1, 15), sku_id=1, cost_history=cost_history)
    assert result1 == 1000.0  # 10 * 100

    # Sale on 2025-02-15 uses second price
    result2 = calc_cogs(qty=10, d=date(2025, 2, 15), sku_id=1, cost_history=cost_history)
    assert result2 == 1100.0  # 10 * 110

    # Sale on 2025-03-15 uses third price
    result3 = calc_cogs(qty=10, d=date(2025, 3, 15), sku_id=1, cost_history=cost_history)
    assert result3 == 1200.0  # 10 * 120


def test_calc_cogs_no_history():
    """Test COGS returns 0 if no cost history."""
    result = calc_cogs(qty=10, d=date(2025, 1, 1), sku_id=1, cost_history=[])
    assert result == 0.0


def test_calc_profit():
    """Test profit calculation."""
    result = calc_profit(revenue_net=10000.0, cogs=6000.0, marketing=1000.0)
    assert result == 3000.0  # 10000 - 6000 - 1000


def test_calc_margin():
    """Test margin percentage calculation."""
    result = calc_margin(profit=3000.0, revenue_net=10000.0)
    assert result == 30.0  # (3000 / 10000) * 100


def test_calc_margin_zero_revenue():
    """Test margin returns 0 if revenue is 0."""
    result = calc_margin(profit=100.0, revenue_net=0.0)
    assert result == 0.0


# =============================================================================
# Inventory/Supply Tests
# =============================================================================


def test_rolling_velocity_simple():
    """Test rolling velocity calculation."""
    qty_by_day = [10, 12, 8, 15, 11, 9, 14]
    result = rolling_velocity(qty_by_day, window=7)
    # (10 + 12 + 8 + 15 + 11 + 9 + 14) / 7 = 79 / 7 ≈ 11.29
    assert result == pytest.approx(11.286, rel=0.01)


def test_rolling_velocity_window_larger_than_data():
    """Test rolling velocity when window > data length."""
    qty_by_day = [10, 12, 8]
    result = rolling_velocity(qty_by_day, window=7)
    # Uses all 3 days: (10 + 12 + 8) / 3 = 10.0
    assert result == 10.0


def test_rolling_velocity_empty():
    """Test rolling velocity with empty data."""
    result = rolling_velocity([], window=7)
    assert result == 0.0


def test_stock_cover_days():
    """Test stock cover days calculation."""
    result = stock_cover_days(on_hand=100, in_transit=50, velocity=10.0)
    # (100 + 50) / 10 = 15 days
    assert result == 15.0


def test_stock_cover_days_zero_velocity():
    """Test stock cover returns infinite (999.0) when velocity is 0."""
    result = stock_cover_days(on_hand=100, in_transit=0, velocity=0.0)
    assert result == 999.0


def test_recommend_supply_basic():
    """Test supply recommendation calculation."""
    result = recommend_supply(
        sv=10.0,  # 10 units per day
        window_days=14,
        on_hand=50,
        in_transit=20,
        safety_coeff=1.5,
        demand_std=3.0,
    )
    # Expected demand: 10 * 14 = 140
    # Safety stock: 1.5 * 3 * √14 ≈ 1.5 * 3 * 3.74 ≈ 16.8 → 17
    # Total need: 140 + 17 = 157
    # Current: 50 + 20 = 70
    # Recommendation: 157 - 70 = 87
    assert result == pytest.approx(87, abs=2)  # Allow ±2 for rounding


def test_recommend_supply_overstocked():
    """Test recommendation returns 0 when already overstocked."""
    result = recommend_supply(
        sv=10.0,
        window_days=14,
        on_hand=200,
        in_transit=50,
        safety_coeff=1.5,
        demand_std=0.0,
    )
    # Need: 10 * 14 = 140
    # Have: 200 + 50 = 250
    # Recommendation: max(0, 140 - 250) = 0
    assert result == 0


def test_recommend_supply_no_safety_stock():
    """Test recommendation without safety stock (std = 0)."""
    result = recommend_supply(
        sv=5.0,
        window_days=28,
        on_hand=50,
        in_transit=0,
        safety_coeff=1.5,
        demand_std=0.0,  # No variability
    )
    # Need: 5 * 28 = 140
    # Safety: 0
    # Have: 50
    # Recommendation: 140 - 50 = 90
    assert result == 90
