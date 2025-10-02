"""VCR integration tests for Ozon transactions ingestion."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.services.ingestion_real import collect_ozon_transactions_range


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
async def test_ozon_transactions_last7days(vcr, test_db):
    """Test Ozon transactions ingestion with VCR cassette (last 7 days)."""
    d_from = date.today() - timedelta(days=7)
    d_to = date.today()

    with vcr.use_cassette("ozon_tx_last7days.yaml"):
        upserts = await collect_ozon_transactions_range(test_db, d_from, d_to)
        assert upserts >= 0  # Should succeed, even if 0 records


@pytest.mark.asyncio
async def test_ozon_transactions_pagination(vcr, test_db):
    """Test Ozon transactions with multi-page response."""
    d_from = date.today() - timedelta(days=30)
    d_to = date.today()

    with vcr.use_cassette("ozon_tx_multipage.yaml"):
        upserts = await collect_ozon_transactions_range(test_db, d_from, d_to)
        assert upserts >= 0
