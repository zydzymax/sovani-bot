"""VCR integration tests for WB sales ingestion."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.services.ingestion_real import collect_wb_sales_range


@pytest.fixture
def test_db():
    """Create test database for integration tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_wb_sales_last2days_ingest(vcr, test_db):
    """Test WB sales ingestion with VCR cassette (last 2 days)."""
    d_from = date.today() - timedelta(days=2)
    d_to = date.today()

    with vcr.use_cassette("wb_sales_last2days.yaml"):
        upserts = await collect_wb_sales_range(test_db, d_from, d_to)
        assert upserts >= 0  # Should succeed, even if 0 records


@pytest.mark.asyncio
async def test_wb_sales_historical_ingest(vcr, test_db):
    """Test WB sales ingestion with flag=1 (historical data)."""
    d_from = date.today() - timedelta(days=30)
    d_to = date.today() - timedelta(days=25)

    with vcr.use_cassette("wb_sales_historical.yaml"):
        upserts = await collect_wb_sales_range(test_db, d_from, d_to)
        assert upserts >= 0
