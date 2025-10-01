"""Telegram bot middleware for request ID tracking and logging.

Provides middleware for aiogram to automatically set request_id and log updates.
"""

from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Update

from app.core.logging import get_logger, set_request_id

log = get_logger("sovani_bot.tg")


class RequestIdMiddleware(BaseMiddleware):
    """Middleware to set request_id for each incoming Telegram update."""

    async def on_pre_process_update(self, update: Update, data: dict) -> None:
        """Set request_id and log incoming update before processing."""
        rid = set_request_id()

        # Determine update type
        update_type = "unknown"
        if update.message:
            update_type = "message"
        elif update.callback_query:
            update_type = "callback_query"
        elif update.inline_query:
            update_type = "inline_query"
        elif update.edited_message:
            update_type = "edited_message"
        elif update.channel_post:
            update_type = "channel_post"

        # Extract user info if available
        user_id = None
        username = None
        chat_id = None

        if update.message:
            user_id = update.message.from_user.id if update.message.from_user else None
            username = update.message.from_user.username if update.message.from_user else None
            chat_id = update.message.chat.id if update.message.chat else None
        elif update.callback_query:
            user_id = (
                update.callback_query.from_user.id if update.callback_query.from_user else None
            )
            username = (
                update.callback_query.from_user.username
                if update.callback_query.from_user
                else None
            )
            if update.callback_query.message:
                chat_id = update.callback_query.message.chat.id

        log.info(
            "update_received",
            extra={
                "request_id": rid,
                "update_type": update_type,
                "user_id": user_id,
                "username": username,
                "chat_id": chat_id,
                "update_id": update.update_id,
            },
        )


__all__ = ["RequestIdMiddleware"]
