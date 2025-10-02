"""AI-powered custom reply generation for atypical reviews."""

from __future__ import annotations

import logging

import openai

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def generate_custom_reply(
    *,
    name: str | None,
    rating: int | None,
    text: str,
    has_media: bool,
) -> str:
    """Generate personalized AI reply for atypical review.

    Args:
        name: Customer name (optional)
        rating: Review rating (1-5 stars)
        text: Review text content
        has_media: Whether review contains photos/videos

    Returns:
        Generated reply text

    AI Prompt includes:
        - Greeting with name if available (never use "покупатель")
        - Acknowledgment of actual rating (1-5 stars)
        - Response appropriate to sentiment (positive/neutral/negative)
        - Mention of media if present
        - Call to action for future detailed reviews with photos/videos
        - Invitation to return to SoVAni

    Examples:
        >>> import asyncio
        >>> # This would call OpenAI in production
        >>> # reply = asyncio.run(generate_custom_reply(
        >>> #     name="Анна",
        >>> #     rating=4,
        >>> #     text="Хорошее качество, но доставка долгая",
        >>> #     has_media=True
        >>> # ))

    """
    settings = get_settings()

    # Build context-aware prompt
    prompt = _build_prompt(
        name=name,
        rating=rating,
        text=text,
        has_media=has_media,
    )

    try:
        # Use OpenAI API
        openai.api_key = settings.openai_api_key

        response = await openai.ChatCompletion.acreate(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты — помощник службы поддержки SoVAni. "
                        "Отвечай на отзывы покупателей вежливо и профессионально. "
                        "НИКОГДА не используй слово 'покупатель' или 'клиент'. "
                        "Если есть имя — обращайся по имени. "
                        "Учитывай фактическую оценку (звёзды) и тон отзыва. "
                        "Приглашай к будущим покупкам и развёрнутым отзывам с фото/видео."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )

        reply = response.choices[0].message.content.strip()

        # Ensure SoVAni branding is present
        if "SoVAni" not in reply and "sovani" not in reply.lower():
            reply += " Команда SoVAni."

        logger.info(f"Generated custom reply for rating={rating}, has_media={has_media}")
        return reply

    except Exception as e:
        logger.error(f"Failed to generate AI reply: {e}")
        # Fallback to generic professional response
        return _fallback_reply(name=name, rating=rating, has_media=has_media)


def _build_prompt(
    *,
    name: str | None,
    rating: int | None,
    text: str,
    has_media: bool,
) -> str:
    """Build AI prompt with review context.

    Args:
        name: Customer name
        rating: Review rating
        text: Review text
        has_media: Has media flag

    Returns:
        Formatted prompt for AI

    """
    prompt_parts = []

    # 1. Review details
    prompt_parts.append("Отзыв покупателя:")
    if name:
        prompt_parts.append(f"Имя: {name}")
    prompt_parts.append(f"Оценка: {rating}★")
    prompt_parts.append(f"Текст: {text}")
    if has_media:
        prompt_parts.append("К отзыву приложены фото/видео.")

    # 2. Instructions
    prompt_parts.append("\nТвоя задача:")
    if name:
        prompt_parts.append(f"1. Обратись к покупателю по имени ({name}).")
    else:
        prompt_parts.append("1. Начни с нейтрального приветствия (без 'покупатель').")

    prompt_parts.append("2. Поблагодари за отзыв.")

    # 3. Rating-specific response
    if rating in {4, 5}:
        prompt_parts.append("3. Вырази радость, что всё понравилось.")
    elif rating == 3:
        prompt_parts.append("3. Вырази готовность улучшаться и учесть замечания.")
    elif rating in {1, 2}:
        prompt_parts.append("3. Вырази сожаление о проблеме и предложи помощь/разъяснения.")

    # 4. Media acknowledgment
    if has_media:
        prompt_parts.append("4. Поблагодари за приложенные фото/видео — это помогает другим.")
    else:
        prompt_parts.append("4. Мягко попроси дополнить отзыв фото/видео в будущем (если захочет).")

    # 5. Call to action
    prompt_parts.append("5. Пригласи вернуться за покупками в SoVAni.")

    # 6. Constraints
    prompt_parts.append("\nОграничения:")
    prompt_parts.append("- НЕ используй слова 'покупатель', 'клиент'.")
    prompt_parts.append("- Ответ должен быть коротким (2-4 предложения).")
    prompt_parts.append("- Тон должен соответствовать оценке (позитив/нейтрал/извинение).")
    prompt_parts.append("- Обязательно упомяни бренд 'SoVAni'.")

    return "\n".join(prompt_parts)


def _fallback_reply(
    *,
    name: str | None,
    rating: int | None,
    has_media: bool,
) -> str:
    """Generate fallback reply if AI fails.

    Args:
        name: Customer name
        rating: Review rating
        has_media: Has media flag

    Returns:
        Safe fallback reply

    """
    greeting = f"{name}, спасибо" if name else "Спасибо"

    if rating in {4, 5}:
        response = f"{greeting} за ваш отзыв! Нам очень приятно, что вы довольны покупкой. "
    elif rating in {1, 2}:
        response = (
            f"{greeting} за обратную связь. Нам жаль, что возникли сложности. "
            "Пожалуйста, напишите нам подробнее, чтобы мы могли помочь. "
        )
    else:
        response = f"{greeting} за ваше мнение! Мы учтём ваши замечания. "

    if has_media:
        response += "Ценим, что вы добавили фото/видео. "
    else:
        response += "Будем благодарны, если вы дополните отзыв фото или видео. "

    response += "Ждём вас снова в SoVAni!"

    return response
