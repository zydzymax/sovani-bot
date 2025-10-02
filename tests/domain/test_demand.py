"""Tests for demand forecasting module."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, DailySales, SKU, Warehouse
from app.domain.supply.demand import demand_stdev, forecast_qty, rolling_sv, stock_cover_days


@pytest.fixture
def db_session():
    """Create in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_sku(db_session):
    """Create test SKU."""
    sku = SKU(id=1, marketplace="WB", nm_id="12345", article="TEST-001")
    db_session.add(sku)
    db_session.commit()
    return sku


@pytest.fixture
def test_warehouse(db_session):
    """Create test warehouse."""
    wh = Warehouse(id=1, marketplace="WB", code="Казань", name="Казань")
    db_session.add(wh)
    db_session.commit()
    return wh


def test_rolling_sv_calculates_average(db_session, test_sku, test_warehouse):
    """SV should be total qty / days."""
    # Create 14 days of sales: total = 70 units
    end_date = date.today()
    for i in range(14):
        d = end_date - timedelta(days=i)
        sale = DailySales(
            d=d,
            sku_id=test_sku.id,
            warehouse_id=test_warehouse.id,
            qty=5,
            src_hash=f"hash_{i}",
        )
        db_session.add(sale)
    db_session.commit()

    sv = rolling_sv(db_session, test_sku.id, test_warehouse.id, 14)

    assert sv == 5.0  # 70 / 14 = 5.0


def test_rolling_sv_no_sales_returns_zero(db_session, test_sku, test_warehouse):
    """SV should be 0 if no sales."""
    sv = rolling_sv(db_session, test_sku.id, test_warehouse.id, 14)
    assert sv == 0.0


def test_forecast_qty_rounds_up(db_session):
    """Forecast should round up fractional values."""
    # sv=3.5, window=14 → 3.5 * 14 = 49 → ceil(49) = 49
    result = forecast_qty(3.5, 14)
    assert result == 49

    # sv=3.2, window=10 → 3.2 * 10 = 32 → ceil(32) = 32
    result = forecast_qty(3.2, 10)
    assert result == 32

    # sv=3.3, window=10 → 3.3 * 10 = 33 → ceil(33) = 33
    result = forecast_qty(3.3, 10)
    assert result == 33


def test_forecast_qty_zero_sv_returns_zero(db_session):
    """Forecast should be 0 if SV is 0."""
    result = forecast_qty(0.0, 14)
    assert result == 0


def test_stock_cover_days_calculation(db_session):
    """Coverage = (on_hand + in_transit) / sv."""
    # on_hand=20, in_transit=10, sv=3.5 → 30 / 3.5 = 8.57 days
    cover = stock_cover_days(20, 10, 3.5)
    assert abs(cover - 8.571) < 0.01


def test_stock_cover_days_zero_sv_returns_inf(db_session):
    """Coverage should be inf if sv=0 and stock>0."""
    cover = stock_cover_days(20, 10, 0.0)
    assert cover == float("inf")


def test_stock_cover_days_zero_stock_and_sv_returns_zero(db_session):
    """Coverage should be 0 if both stock and sv are 0."""
    cover = stock_cover_days(0, 0, 0.0)
    assert cover == 0.0


def test_demand_stdev_with_variation(db_session, test_sku, test_warehouse):
    """Stdev should capture demand variability."""
    # Create sales with variation: [3, 5, 2, 4, 6, 3, 5]
    quantities = [3, 5, 2, 4, 6, 3, 5]
    end_date = date.today()

    for i, qty in enumerate(quantities):
        d = end_date - timedelta(days=i)
        sale = DailySales(
            d=d,
            sku_id=test_sku.id,
            warehouse_id=test_warehouse.id,
            qty=qty,
            src_hash=f"hash_{i}",
        )
        db_session.add(sale)
    db_session.commit()

    stdev = demand_stdev(db_session, test_sku.id, test_warehouse.id, 7)

    # Manual calculation: mean=4, variance=[(3-4)^2 + (5-4)^2 + ...]/6 = 10/6 = 1.67
    # stdev = sqrt(1.67) ≈ 1.29
    assert 1.0 < stdev < 2.0


def test_demand_stdev_constant_demand_returns_zero(db_session, test_sku, test_warehouse):
    """Stdev should be 0 for constant demand."""
    # Create 7 days of constant sales: all qty=5
    end_date = date.today()
    for i in range(7):
        d = end_date - timedelta(days=i)
        sale = DailySales(
            d=d,
            sku_id=test_sku.id,
            warehouse_id=test_warehouse.id,
            qty=5,
            src_hash=f"hash_{i}",
        )
        db_session.add(sale)
    db_session.commit()

    stdev = demand_stdev(db_session, test_sku.id, test_warehouse.id, 7)

    assert stdev == 0.0
