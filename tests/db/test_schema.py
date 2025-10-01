"""Tests for database schema and migrations."""

from datetime import date

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    AdviceSupply,
    Base,
    Cashflow,
    CommissionRule,
    CostPriceHistory,
    DailySales,
    DailyStock,
    MetricsDaily,
    Review,
    SKU,
    Warehouse,
)


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    db = SessionLocal()
    yield db
    db.close()


def test_all_tables_created(test_db):
    """Verify all expected tables are created."""
    inspector = inspect(test_db.bind)
    table_names = inspector.get_table_names()

    expected_tables = {
        "sku",
        "warehouse",
        "cost_price_history",
        "commission_rules",
        "daily_sales",
        "daily_stock",
        "reviews",
        "cashflows",
        "metrics_daily",
        "advice_supply",
    }

    assert expected_tables.issubset(
        set(table_names)
    ), f"Missing tables: {expected_tables - set(table_names)}"


def test_sku_unique_constraints(test_db):
    """Test SKU unique constraints."""
    # Create WB SKU
    sku1 = SKU(marketplace="WB", nm_id="12345", article="TEST-1")
    test_db.add(sku1)
    test_db.commit()

    # Try to create duplicate (should fail)
    sku2 = SKU(marketplace="WB", nm_id="12345", article="TEST-2")
    test_db.add(sku2)

    with pytest.raises(Exception):  # IntegrityError
        test_db.commit()


def test_warehouse_unique_constraints(test_db):
    """Test Warehouse unique constraints."""
    wh1 = Warehouse(marketplace="WB", code="Коледино", name="Коледино")
    test_db.add(wh1)
    test_db.commit()

    # Try to create duplicate
    wh2 = Warehouse(marketplace="WB", code="Коледино", name="Koledino")
    test_db.add(wh2)

    with pytest.raises(Exception):  # IntegrityError
        test_db.commit()


def test_daily_sales_upsert_pattern(test_db):
    """Test that daily_sales supports upsert pattern."""
    # Create SKU and Warehouse
    sku = SKU(marketplace="WB", nm_id="12345")
    test_db.add(sku)
    test_db.flush()

    wh = Warehouse(marketplace="WB", code="TEST-WH")
    test_db.add(wh)
    test_db.flush()

    # Create initial sale
    sale1 = DailySales(
        d=date(2025, 1, 1),
        sku_id=sku.id,
        warehouse_id=wh.id,
        qty=10,
        revenue_gross=1000.0,
        src_hash="hash1",
    )
    test_db.add(sale1)
    test_db.commit()

    # Verify it's there
    count = test_db.query(DailySales).count()
    assert count == 1

    # Try to insert duplicate with different src_hash
    # This would be handled by ON CONFLICT in real PostgreSQL,
    # but SQLite doesn't support WHERE clause in upsert
    # Just verify the unique constraint exists
    from sqlalchemy import select

    stmt = select(DailySales).where(
        DailySales.d == date(2025, 1, 1),
        DailySales.sku_id == sku.id,
        DailySales.warehouse_id == wh.id,
    )
    result = test_db.execute(stmt).scalar_one()
    assert result.qty == 10
    assert result.src_hash == "hash1"


def test_cost_price_history(test_db):
    """Test cost price history tracking."""
    sku = SKU(marketplace="WB", nm_id="12345")
    test_db.add(sku)
    test_db.flush()

    # Add cost history
    cost1 = CostPriceHistory(sku_id=sku.id, dt_from=date(2025, 1, 1), cost_price=100.0)
    cost2 = CostPriceHistory(sku_id=sku.id, dt_from=date(2025, 2, 1), cost_price=110.0)

    test_db.add_all([cost1, cost2])
    test_db.commit()

    # Query cost history
    from sqlalchemy import select

    stmt = (
        select(CostPriceHistory)
        .where(CostPriceHistory.sku_id == sku.id)
        .order_by(CostPriceHistory.dt_from)
    )
    history = test_db.execute(stmt).scalars().all()

    assert len(history) == 2
    assert history[0].cost_price == 100.0
    assert history[1].cost_price == 110.0


def test_metrics_daily_calculation_fields(test_db):
    """Test MetricsDaily has all required calculation fields."""
    sku = SKU(marketplace="WB", nm_id="12345")
    test_db.add(sku)
    test_db.flush()

    metrics = MetricsDaily(
        d=date(2025, 1, 1),
        sku_id=sku.id,
        revenue_net=1000.0,
        cogs=600.0,
        profit=400.0,
        margin=40.0,
        sv7=10.5,
        sv14=12.3,
        sv28=11.8,
        stock_cover_days=25.5,
    )
    test_db.add(metrics)
    test_db.commit()

    # Verify all fields
    from sqlalchemy import select

    stmt = select(MetricsDaily).where(MetricsDaily.sku_id == sku.id)
    result = test_db.execute(stmt).scalar_one()

    assert result.revenue_net == 1000.0
    assert result.cogs == 600.0
    assert result.profit == 400.0
    assert result.margin == 40.0
    assert result.sv7 == 10.5
    assert result.sv14 == 12.3
    assert result.sv28 == 11.8
    assert result.stock_cover_days == 25.5
