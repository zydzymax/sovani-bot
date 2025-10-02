"""Tests for review classifier."""

from __future__ import annotations

from app.domain.reviews.classifier import classify_review


def test_typical_positive_empty_text():
    """5-star review with no text → typical_positive."""
    result = classify_review(rating=5, text="", has_media=False)
    assert result == "typical_positive"


def test_typical_positive_short_stamp():
    """5-star review with 'супер' → typical_positive."""
    result = classify_review(rating=5, text="Супер!", has_media=False)
    assert result == "typical_positive"


def test_typical_negative_short_stamp():
    """1-star review with 'маломерит' → typical_negative."""
    result = classify_review(rating=1, text="Маломерит", has_media=False)
    assert result == "typical_negative"


def test_typical_neutral():
    """3-star review with short text → typical_neutral."""
    result = classify_review(rating=3, text="Нормально", has_media=False)
    assert result == "typical_neutral"


def test_atypical_has_media():
    """Any review with media → atypical."""
    result = classify_review(rating=5, text="Супер", has_media=True)
    assert result == "atypical"


def test_atypical_long_text():
    """Long text (>40 chars) → atypical."""
    result = classify_review(
        rating=4,
        text="Очень понравилось качество ткани и быстрая доставка",
        has_media=False,
    )
    assert result == "atypical"


def test_typical_positive_4stars():
    """4-star with short text → typical_positive."""
    result = classify_review(rating=4, text="Хорошо", has_media=False)
    assert result == "typical_positive"


def test_typical_negative_2stars():
    """2-star with short negative → typical_negative."""
    result = classify_review(rating=2, text="Плохо", has_media=False)
    assert result == "typical_negative"


def test_atypical_mixed_signals():
    """Short positive text with low rating → might be atypical."""
    # With only 1-2 words, should still be typical_negative based on rating
    result = classify_review(rating=1, text="Супер", has_media=False)
    # This is edge case - positive word with negative rating
    # Based on our logic, short text + rating=1 → typical_negative
    assert result in {"typical_negative", "atypical"}


def test_empty_text_neutral_rating():
    """Empty text with 3 stars → typical_neutral."""
    result = classify_review(rating=3, text="", has_media=False)
    assert result == "typical_neutral"


def test_emoji_only():
    """Emoji-only review → typical based on rating."""
    result = classify_review(rating=5, text="👍", has_media=False)
    assert result == "typical_positive"


def test_multiple_short_words():
    """4 words, positive rating → typical_positive."""
    result = classify_review(rating=5, text="Все отлично спасибо большое", has_media=False)
    # "Все отлично спасибо большое" = 4 words, should be typical
    assert result == "typical_positive"
