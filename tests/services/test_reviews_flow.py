"""E2E tests for reviews flow: fetch → classify → generate → send."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Review
from app.services.reviews_service import build_reply_for_review, mark_reply_sent


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def typical_positive_review(db_session):
    """Create typical positive review."""
    review = Review(
        review_id="wb_12345",
        marketplace="WB",
        sku_id=None,
        rating=5,
        text="Супер!",
        created_at_utc=datetime.now(UTC),
        has_media=False,
        reply_status=None,
    )
    db_session.add(review)
    db_session.commit()
    return review


@pytest.fixture
def atypical_review(db_session):
    """Create atypical review (long text)."""
    review = Review(
        review_id="ozon_67890",
        marketplace="OZON",
        sku_id=None,
        rating=4,
        text="Очень понравилось качество ткани, быстрая доставка, хороший размер",
        created_at_utc=datetime.now(UTC),
        has_media=False,
        reply_status=None,
    )
    db_session.add(review)
    db_session.commit()
    return review


@pytest.mark.asyncio
async def test_typical_review_uses_template(typical_positive_review, db_session):
    """Typical positive review → template reply."""
    reply_text = await build_reply_for_review(typical_positive_review.review_id, db_session)

    # Should use template (contains SoVAni)
    assert "SoVAni" in reply_text
    assert "покупатель" not in reply_text.lower()
    assert len(reply_text) > 20


@pytest.mark.asyncio
async def test_atypical_review_uses_ai(atypical_review, db_session, monkeypatch):
    """Atypical review → AI-generated reply."""
    mock_response = Mock(choices=[Mock(message=Mock(content="Спасибо за ваш подробный отзыв!"))])
    monkeypatch.setattr("openai.ChatCompletion.acreate", AsyncMock(return_value=mock_response))

    reply_text = await build_reply_for_review(atypical_review.review_id, db_session)

    assert len(reply_text) > 0
    assert "покупатель" not in reply_text.lower()


@pytest.mark.asyncio
async def test_mark_reply_sent_updates_status(typical_positive_review, db_session):
    """Marking reply as sent updates review status."""
    reply_text = "Спасибо за ваш отзыв!"

    await mark_reply_sent(db_session, typical_positive_review.review_id, reply_text)

    # Check review updated
    stmt = select(Review).where(Review.review_id == typical_positive_review.review_id)
    updated = db_session.execute(stmt).scalar_one()

    assert updated.reply_status == "sent"
    assert updated.reply_text == reply_text
    assert updated.replied_at_utc is not None
    assert updated.reply_id == "local"


@pytest.mark.asyncio
async def test_review_not_found_raises_error(db_session):
    """Non-existent review raises ValueError."""
    with pytest.raises(ValueError, match="Review not found"):
        await build_reply_for_review("nonexistent_id", db_session)


@pytest.mark.asyncio
async def test_typical_negative_uses_template(db_session):
    """Typical negative review → template reply."""
    review = Review(
        review_id="wb_neg_1",
        marketplace="WB",
        sku_id=None,
        rating=1,
        text="Маломерит",
        created_at_utc=datetime.now(UTC),
        has_media=False,
        reply_status=None,
    )
    db_session.add(review)
    db_session.commit()

    reply_text = await build_reply_for_review(review.review_id, db_session)

    assert "SoVAni" in reply_text
    assert "покупатель" not in reply_text.lower()


@pytest.mark.asyncio
async def test_review_with_media_is_atypical(db_session, monkeypatch):
    """Review with media → AI (atypical)."""
    review = Review(
        review_id="ozon_media_1",
        marketplace="OZON",
        sku_id=None,
        rating=5,
        text="Класс",
        created_at_utc=datetime.now(UTC),
        has_media=True,
        reply_status=None,
    )
    db_session.add(review)
    db_session.commit()

    mock_response = Mock(choices=[Mock(message=Mock(content="Спасибо за фото!"))])
    monkeypatch.setattr("openai.ChatCompletion.acreate", AsyncMock(return_value=mock_response))

    reply_text = await build_reply_for_review(review.review_id, db_session)

    assert len(reply_text) > 0
