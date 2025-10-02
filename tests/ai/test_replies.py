"""Tests for AI reply generation."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from app.ai.replies import generate_custom_reply


@pytest.mark.asyncio
async def test_ai_reply_with_name(monkeypatch):
    """AI reply includes customer name."""
    mock_response = Mock(
        choices=[Mock(message=Mock(content="Анна, спасибо за ваш подробный отзыв!"))]
    )
    mock_create = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("openai.ChatCompletion.acreate", mock_create)

    result = await generate_custom_reply(
        name="Анна", rating=4, text="Длинный подробный отзыв о качестве", has_media=True
    )

    assert "Анна" in result
    # Verify OpenAI was called
    assert mock_create.called


@pytest.mark.asyncio
async def test_ai_reply_without_name(monkeypatch):
    """AI reply without name uses generic greeting."""
    mock_response = Mock(choices=[Mock(message=Mock(content="Спасибо за ваш отзыв!"))])
    mock_create = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("openai.ChatCompletion.acreate", mock_create)

    result = await generate_custom_reply(
        name=None, rating=5, text="Отличное качество ткани", has_media=False
    )

    assert len(result) > 0
    assert mock_create.called


@pytest.mark.asyncio
async def test_ai_reply_never_uses_buyer_word(monkeypatch):
    """AI reply never contains 'покупатель'."""
    mock_response = Mock(choices=[Mock(message=Mock(content="Спасибо за ваш отзыв о SoVAni!"))])
    monkeypatch.setattr("openai.ChatCompletion.acreate", AsyncMock(return_value=mock_response))

    result = await generate_custom_reply(
        name=None, rating=3, text="Средне, размер не тот", has_media=False
    )

    assert "покупатель" not in result.lower()


@pytest.mark.asyncio
async def test_ai_reply_handles_low_rating(monkeypatch):
    """AI reply for low rating review."""
    mock_response = Mock(
        choices=[Mock(message=Mock(content="Извините за доставленные неудобства..."))]
    )
    monkeypatch.setattr("openai.ChatCompletion.acreate", AsyncMock(return_value=mock_response))

    result = await generate_custom_reply(
        name=None, rating=1, text="Очень плохое качество, разочарован", has_media=False
    )

    assert len(result) > 0


@pytest.mark.asyncio
async def test_ai_reply_acknowledges_media(monkeypatch):
    """AI reply acknowledges presence of media."""
    mock_response = Mock(choices=[Mock(message=Mock(content="Спасибо за отзыв с фото!"))])
    monkeypatch.setattr("openai.ChatCompletion.acreate", AsyncMock(return_value=mock_response))

    result = await generate_custom_reply(name=None, rating=5, text="Отличный товар", has_media=True)

    assert len(result) > 0


@pytest.mark.asyncio
async def test_ai_fallback_on_error(monkeypatch):
    """Fallback reply when AI fails."""
    # Simulate OpenAI API error
    monkeypatch.setattr(
        "openai.ChatCompletion.acreate", AsyncMock(side_effect=Exception("API Error"))
    )

    result = await generate_custom_reply(name=None, rating=4, text="Хороший товар", has_media=False)

    # Should return fallback, not crash
    assert len(result) > 0
    assert "SoVAni" in result
