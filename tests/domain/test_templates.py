"""Tests for SoVAni templates."""

from __future__ import annotations

import random

from app.domain.reviews.templates import choose_template, personalize_reply


def test_choose_positive_template():
    """Positive template contains SoVAni."""
    random.seed(42)
    template = choose_template("typical_positive")
    assert "SoVAni" in template
    assert "покупатель" not in template.lower()


def test_choose_negative_template():
    """Negative template contains SoVAni."""
    random.seed(42)
    template = choose_template("typical_negative")
    assert "SoVAni" in template
    assert "покупатель" not in template.lower()


def test_personalize_with_name():
    """Personalization adds name."""
    result = personalize_reply("Анна", "Спасибо за ваш отзыв!")
    assert result.startswith("Анна,")
    assert "покупатель" not in result.lower()


def test_personalize_without_name():
    """No name → template as-is."""
    template = "Спасибо за ваш отзыв!"
    result = personalize_reply(None, template)
    assert result == template
    assert "покупатель" not in result.lower()


def test_no_buyer_word_in_templates():
    """Ensure 'покупатель' never appears."""
    for kind in ["typical_positive", "typical_negative", "typical_neutral"]:
        for _ in range(10):
            template = choose_template(kind)
            assert "покупатель" not in template.lower()
