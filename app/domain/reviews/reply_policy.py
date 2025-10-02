"""Reply policy for customer reviews."""

from __future__ import annotations


def build_reply_prompt(rating: int, text: str) -> str:
    """Build AI prompt for generating review reply based on rating and content.

    Args:
        rating: Star rating (1-5)
        text: Review text from customer

    Returns:
        Prompt for AI reply generation

    """
    base = "Ты — вежливый саппорт бренда. Ответь кратко, по делу, на русском."

    if rating >= 4:
        return (
            f"{base}\n"
            f"Поблагодари за отзыв {rating}★, подчеркни сильные стороны, пригласи задать вопросы.\n"
            f"Отзыв: «{text}»"
        )

    if rating == 3:
        return (
            f"{base}\n"
            f"Нейтрально-благодарственный тон. Спроси, что улучшить.\n"
            f"Отзыв: «{text}»"
        )

    # rating <= 2: negative review
    return f"{base}\n" f"Извинись, предложи решение/обмен/возврат и поддержку.\n" f"Отзыв: «{text}»"
