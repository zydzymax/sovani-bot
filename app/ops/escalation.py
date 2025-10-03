"""Review SLA escalation notifications (Stage 18)."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Bot

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def notify_overdue_reviews(
    items: list[dict[str, Any]],
    chat_ids: list[int],
    batch_size: int = 30,
) -> int:
    """Send batched escalation notifications for overdue reviews.

    Args:
        items: List of overdue review dicts from find_overdue_reviews()
        chat_ids: Telegram chat IDs to notify
        batch_size: Reviews per message (default: 30)

    Returns:
        Number of messages sent

    Format:
        Header: "⏰ SLA: просроченные отзывы (N)"
        Rows: review_id | ★rating | age(h) | ai_needed | marketplace | SKU/article
        Links: clickable if available

    """
    if not items:
        logger.info("No overdue reviews to escalate")
        return 0

    if not chat_ids:
        logger.warning("No chat IDs configured for escalation (SLA_NOTIFY_CHAT_IDS)")
        return 0

    settings = get_settings()
    bot = Bot(token=settings.telegram_token)

    messages_sent = 0

    # Split into batches
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]

        # Build message header
        msg = f"⏰ **SLA: просроченные отзывы ({len(batch)})**\n\n"
        msg += "Требуют первого ответа (без reply):\n\n"

        # Build table
        for item in batch:
            rating_stars = "★" * item["rating"]
            ai_flag = "🤖 AI" if item["ai_needed"] else "📝"
            age = f"{item['age_hours']:.1f}ч"

            # Format row
            row = (
                f"• ID {item['review_id']} | {rating_stars} | {age} | {ai_flag} | "
                f"{item['marketplace']} | {item['article']}"
            )

            # Add link if available
            if item.get("link"):
                row += f"\n  [Открыть отзыв]({item['link']})"

            msg += row + "\n\n"

        msg += f"\nВсего просрочено: **{len(items)}** отзывов"

        # Send to all configured chats
        for chat_id in chat_ids:
            try:
                bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                logger.info(f"Sent escalation batch ({len(batch)} reviews) to chat {chat_id}")
            except Exception as e:
                logger.exception(f"Failed to send escalation to chat {chat_id}: {e}")

        messages_sent += 1

    logger.info(f"Escalation complete: {messages_sent} messages sent, {len(items)} reviews total")
    return messages_sent
