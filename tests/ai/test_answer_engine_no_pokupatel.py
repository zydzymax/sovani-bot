"""Tests ensuring Answer Engine never uses forbidden 'покупатель' word (Stage 19 Hardening)."""

from __future__ import annotations

from app.ai.replies import _build_prompt
from app.domain.reviews.templates import (
    get_neutral_template,
    get_positive_template,
    personalize_reply,
)


def test_build_prompt_never_contains_pokupatel() -> None:
    """Test AI prompt explicitly forbids 'покупатель' word."""
    # Test various scenarios
    scenarios = [
        {"name": "Анна", "rating": 5, "text": "Отлично!", "has_media": True},
        {"name": None, "rating": 3, "text": "Нормально", "has_media": False},
        {"name": "Иван", "rating": 1, "text": "Плохо", "has_media": True},
        {"name": None, "rating": 4, "text": "Хорошо", "has_media": False},
    ]

    for scenario in scenarios:
        prompt = _build_prompt(**scenario)

        # Prompt should explicitly forbid using the word (in constraints section)
        assert "НЕ используй" in prompt or "не используй" in prompt.lower()
        assert "покупатель" in prompt.lower()  # Mentioned in constraint, but as prohibition

        # Count occurrences: Should appear exactly in constraint section, not in customer-facing parts
        occurrences = prompt.lower().count("покупатель")
        # Allow only in constraint (1-2 times: "не используй слова покупатель, клиент")
        assert occurrences <= 2, f"Too many 'покупатель' mentions: {occurrences}"


def test_build_prompt_uses_name_when_available() -> None:
    """Test prompt includes customer name when provided."""
    prompt = _build_prompt(name="Мария", rating=5, text="Супер!", has_media=False)

    assert "Мария" in prompt
    assert "по имени" in prompt or "Обратись" in prompt


def test_build_prompt_neutral_greeting_when_no_name() -> None:
    """Test prompt uses neutral greeting when no name available."""
    prompt = _build_prompt(name=None, rating=5, text="Отлично", has_media=False)

    assert "нейтрального приветствия" in prompt or "без 'покупатель'" in prompt


def test_build_prompt_acknowledges_media() -> None:
    """Test prompt acknowledges media presence."""
    prompt_with_media = _build_prompt(name="Петр", rating=5, text="Класс", has_media=True)
    prompt_without_media = _build_prompt(name="Петр", rating=5, text="Класс", has_media=False)

    assert "фото/видео" in prompt_with_media.lower()
    assert "приложены" in prompt_with_media or "Поблагодари за" in prompt_with_media

    # Without media, should suggest adding them
    assert "попроси" in prompt_without_media.lower() or "в будущем" in prompt_without_media


def test_template_personalize_reply_never_adds_pokupatel() -> None:
    """Test template personalization never adds 'покупатель'."""
    template = "Спасибо за ваш отзыв! Рады помочь."

    # With name
    reply_with_name = personalize_reply("Алексей", template)
    assert "покупатель" not in reply_with_name.lower()
    assert "Алексей" in reply_with_name

    # Without name
    reply_without_name = personalize_reply(None, template)
    assert "покупатель" not in reply_without_name.lower()


def test_positive_template_never_contains_pokupatel() -> None:
    """Test positive templates don't contain 'покупатель'."""
    template = get_positive_template(rating=5)

    assert "покупатель" not in template.lower()
    assert len(template) > 0  # Not empty


def test_neutral_template_never_contains_pokupatel() -> None:
    """Test neutral templates don't contain 'покупатель'."""
    template = get_neutral_template(rating=3)

    assert "покупатель" not in template.lower()
    assert len(template) > 0  # Not empty


def test_all_ratings_avoid_pokupatel() -> None:
    """Test templates for all ratings avoid 'покупатель'."""
    for rating in [1, 2, 3, 4, 5]:
        if rating >= 4:
            template = get_positive_template(rating=rating)
        else:
            template = get_neutral_template(rating=rating)

        assert (
            "покупатель" not in template.lower()
        ), f"Rating {rating} template contains 'покупатель'"


def test_build_prompt_constraints_explicit() -> None:
    """Test prompt explicitly lists constraints about forbidden words."""
    prompt = _build_prompt(name=None, rating=5, text="Test", has_media=False)

    # Should have constraints section
    assert "Ограничения:" in prompt or "ограничения" in prompt.lower()

    # Should list forbidden words
    assert "клиент" in prompt.lower()  # Also forbidden
    assert "НЕ используй" in prompt or "не используй" in prompt.lower()
