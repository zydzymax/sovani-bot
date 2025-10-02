"""SoVAni-branded reply templates with personalization."""

from __future__ import annotations

import random

# Positive templates (4-5 stars, short/typical reviews)
POSITIVE_TEMPLATES = [
    "Спасибо за ваш отзыв! ❤️ Очень рады, что вам понравилось. "
    "Будем благодарны, если вы дополните отзыв фото или видео — это поможет другим покупателям. "
    "Ждём вас снова в SoVAni!",
    "Благодарим за оценку! ⭐ Нам важно ваше мнение. "
    "Если появится возможность, добавьте, пожалуйста, фото или видео к отзыву. "
    "С нетерпением ждём ваших новых заказов в SoVAni!",
    "Как приятно видеть положительный отзыв! 🌟 Спасибо за доверие. "
    "Поделитесь фото или видео — так вы поможете другим сделать правильный выбор. "
    "До новых встреч в SoVAni!",
]

# Negative templates (1-2 stars, short/typical reviews)
NEGATIVE_TEMPLATES = [
    "Благодарим за обратную связь. Нам жаль, что вы столкнулись с проблемой. "
    "Не могли бы вы уточнить детали и, если возможно, приложить фото? "
    "Это поможет нам разобраться и улучшить качество. Команда SoVAni всегда на связи.",
    "Примите наши извинения за возникшие неудобства. "
    "Будем признательны, если вы напишете подробнее и прикрепите фото или видео — "
    "так мы сможем быстрее помочь и исправить ситуацию. "
    "Мы ценим каждого клиента SoVAni.",
    "Очень сожалеем о произошедшем. Ваш опыт важен для нас. "
    "Пожалуйста, опишите проблему детальнее и добавьте фото, если это возможно. "
    "Команда SoVAni обязательно учтёт ваш отзыв.",
    "Благодарим за то, что сообщили о проблеме. Нам важно разобраться. "
    "Не могли бы вы дополнить отзыв подробностями и фото? "
    "Это поможет нам улучшить сервис. SoVAni заботится о каждом покупателе.",
]

# Neutral templates (3 stars, short/typical reviews)
NEUTRAL_TEMPLATES = [
    "Спасибо за ваше мнение! Мы всегда стремимся стать лучше. "
    "Если есть что добавить, поделитесь фото или видео — это очень ценно для нас. "
    "Будем рады видеть вас снова в SoVAni!",
    "Благодарим за оценку! Ваш опыт помогает нам развиваться. "
    "Если появятся дополнения или фото, обязательно добавьте их к отзыву. "
    "Ждём вас в SoVAni!",
]


def choose_template(kind: str) -> str:
    """Choose random template for given review type.

    Args:
        kind: Review classification ('typical_positive', 'typical_negative', 'typical_neutral')

    Returns:
        Random template from corresponding group

    Raises:
        ValueError: If kind is not recognized

    Examples:
        >>> random.seed(42)
        >>> t = choose_template('typical_positive')
        >>> 'SoVAni' in t
        True

    """
    if kind == "typical_positive":
        return random.choice(POSITIVE_TEMPLATES)
    elif kind == "typical_negative":
        return random.choice(NEGATIVE_TEMPLATES)
    elif kind == "typical_neutral":
        return random.choice(NEUTRAL_TEMPLATES)
    else:
        raise ValueError(f"Unknown template kind: {kind}")


def personalize_reply(name: str | None, template: str) -> str:
    """Personalize template with customer name if available.

    Args:
        name: Customer name (optional)
        template: Template text

    Returns:
        Personalized reply text

    Rules:
        - If name is provided: prepend "{Name}, "
        - If no name: use template as-is (already has neutral greeting)
        - Never use "покупатель" (buyer) - templates already avoid this

    Examples:
        >>> personalize_reply("Анна", "Спасибо за ваш отзыв!")
        'Анна, спасибо за ваш отзыв!'
        >>> personalize_reply(None, "Спасибо за ваш отзыв!")
        'Спасибо за ваш отзыв!'
        >>> personalize_reply("Иван", "Благодарим за оценку!")
        'Иван, благодарим за оценку!'

    """
    if not name or not name.strip():
        # No name - return template as-is
        return template

    # Normalize name (capitalize first letter)
    name_normalized = name.strip()
    if name_normalized:
        name_normalized = name_normalized[0].upper() + name_normalized[1:]

    # Prepend name to template (lowercase first letter of template)
    if template:
        template_lower = (
            template[0].lower() + template[1:] if len(template) > 1 else template.lower()
        )
        return f"{name_normalized}, {template_lower}"

    return template
