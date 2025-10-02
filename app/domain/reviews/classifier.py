"""Review classification for answer engine."""

from __future__ import annotations

# Словарь коротких штампов для типичных отзывов
TYPICAL_POSITIVE_STAMPS = {
    "супер",
    "отлично",
    "хорошо",
    "класс",
    "ок",
    "норм",
    "огонь",
    "топ",
    "👍",
    "🔥",
    "❤️",
    "спасибо",
    "thanks",
}

TYPICAL_NEGATIVE_STAMPS = {
    "плохо",
    "ужас",
    "не то",
    "маломерит",
    "большемерит",
    "брак",
    "не понравилось",
    "разочарование",
    "👎",
}

TYPICAL_NEUTRAL_STAMPS = {
    "нормально",
    "средне",
    "обычно",
    "так себе",
}


def classify_review(
    *,
    rating: int | None,
    text: str | None,
    has_media: bool,
) -> str:
    """Classify review as typical or atypical.

    Args:
        rating: Review rating (1-5 stars)
        text: Review text content
        has_media: Whether review contains photos/videos

    Returns:
        One of: 'typical_positive', 'typical_negative', 'typical_neutral', 'atypical'

    Classification rules:
        - atypical: has_media=True OR text length > 40 chars
        - typical_positive: rating in {4,5} AND text short (≤4 words) or empty
        - typical_negative: rating in {1,2} AND text short (≤4 words) or matches stamps
        - typical_neutral: rating=3 AND text short (≤4 words)

    Examples:
        >>> classify_review(rating=5, text="Супер!", has_media=False)
        'typical_positive'
        >>> classify_review(rating=1, text="Маломерит", has_media=False)
        'typical_negative'
        >>> classify_review(rating=4, text="Очень понравилось качество ткани", has_media=False)
        'atypical'
        >>> classify_review(rating=5, text="Отлично", has_media=True)
        'atypical'

    """
    # Rule 1: Has media → always atypical
    if has_media:
        return "atypical"

    # Normalize text
    text_normalized = (text or "").strip().lower()
    text_length = len(text_normalized)

    # Rule 2: Long text (>40 chars) → atypical
    if text_length > 40:
        return "atypical"

    # Count words (split by spaces and filter empty)
    words = [w for w in text_normalized.split() if w]
    word_count = len(words)

    # Rule 3: Empty or very short text
    if text_length == 0 or word_count == 0:
        # Default to positive for high ratings, neutral for mid, negative for low
        if rating in {4, 5}:
            return "typical_positive"
        elif rating in {1, 2}:
            return "typical_negative"
        else:
            return "typical_neutral"

    # Rule 4: Short text (≤4 words) - check if matches stamps
    if word_count <= 4:
        # Check if any word matches known stamps
        text_words_set = set(words)

        if rating in {4, 5}:
            # Positive rating: check if matches positive stamps or no negative stamps
            if text_words_set & TYPICAL_POSITIVE_STAMPS:
                return "typical_positive"
            elif not (text_words_set & TYPICAL_NEGATIVE_STAMPS):
                return "typical_positive"

        elif rating in {1, 2}:
            # Negative rating: check if matches negative stamps or no positive stamps
            if text_words_set & TYPICAL_NEGATIVE_STAMPS:
                return "typical_negative"
            elif not (text_words_set & TYPICAL_POSITIVE_STAMPS):
                return "typical_negative"

        elif rating == 3:
            # Neutral rating
            if text_words_set & TYPICAL_NEUTRAL_STAMPS:
                return "typical_neutral"
            else:
                return "typical_neutral"

    # Rule 5: Text is short but doesn't match clear patterns → atypical
    # (More than 4 words but less than 40 chars, or mixed signals)
    return "atypical"
