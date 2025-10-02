"""Telegram handlers for review management."""

from __future__ import annotations

from contextlib import suppress

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.logging import get_logger, set_request_id
from app.db.session import SessionLocal
from app.services.reviews_service import (
    build_reply_for_review,
    fetch_pending_reviews,
    mark_reply_sent,
    post_reply,
)

log = get_logger(__name__)


def _kb_for_review(review_id: str) -> InlineKeyboardMarkup:
    """Keyboard for new review: generate draft button."""
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("📝 Сгенерировать ответ", callback_data=f"rev_draft:{review_id}"),
    )
    return kb


def _kb_for_draft(review_id: str) -> InlineKeyboardMarkup:
    """Keyboard for draft preview: send or regenerate."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Отправить", callback_data=f"rev_send:{review_id}"),
        InlineKeyboardButton("🔄 Обновить драфт", callback_data=f"rev_draft:{review_id}"),
    )
    return kb


async def cmd_reviews(message: types.Message):
    """Handle /reviews command - show pending reviews.

    Shows up to 10 pending reviews with generate button.
    """
    set_request_id()  # Correlation ID for logs

    with SessionLocal() as db:
        reviews = await fetch_pending_reviews(db, limit=10)

    if not reviews:
        return await message.answer("Новых отзывов нет ✅")

    for r in reviews:
        # Header: rating + date
        head = f"⭐{r.rating or '—'} | {r.created_at_utc:%Y-%m-%d} | {r.marketplace or 'N/A'}"

        # Text preview (truncate if long)
        text = (r.text or "").strip()
        preview = (text[:400] + "…") if text and len(text) > 400 else (text or "(без текста)")

        await message.answer(
            f"{head}\n\n{preview}",
            reply_markup=_kb_for_review(r.review_id),
        )


async def cb_draft(call: types.CallbackQuery):
    """Handle callback for generating reply draft.

    Uses Answer Engine (Stage 12) to generate template or AI reply.
    Shows preview with send/regenerate buttons.
    """
    set_request_id()

    try:
        _, rid = call.data.split(":", 1)
        await call.answer("Готовлю драфт…")

        # Generate reply using Answer Engine
        with SessionLocal() as db:
            draft = await build_reply_for_review(rid, db)

        # Show preview with actions
        await call.message.answer(
            f"📄 Предпросмотр ответа:\n\n{draft}",
            reply_markup=_kb_for_draft(rid),
        )

    except ValueError as e:
        log.warning("draft_not_found", extra={"rid": rid, "error": str(e)})
        with suppress(Exception):
            await call.answer("Отзыв не найден", show_alert=True)

    except Exception as e:
        log.error("draft_error", extra={"rid": rid, "error": str(e)}, exc_info=True)
        with suppress(Exception):
            await call.answer("Не удалось подготовить драфт", show_alert=True)


async def cb_send(call: types.CallbackQuery):
    """Handle callback for sending reply.

    Posts reply to marketplace (or marks locally if no API) and updates DB.
    """
    set_request_id()

    try:
        _, rid = call.data.split(":", 1)

        # Generate reply (same as draft)
        with SessionLocal() as db:
            draft = await build_reply_for_review(rid, db)

            # Fetch review for post_reply
            reviews = await fetch_pending_reviews(db, limit=100)
            review = next((x for x in reviews if x.review_id == rid), None)

            if not review:
                await call.answer("Отзыв не найден", show_alert=True)
                return

            # Post to marketplace (stub - just logs, no real API)
            ok = await post_reply(review, draft)

            if ok:
                # Mark as sent in DB
                await mark_reply_sent(db, review.review_id, draft)
                await call.message.answer(f"✅ Ответ отправлен:\n\n{draft}")
            else:
                await call.message.answer(f"⚠️ Не удалось отправить ответ:\n\n{draft}")

        await call.answer()

    except ValueError as e:
        log.warning("send_not_found", extra={"rid": rid, "error": str(e)})
        with suppress(Exception):
            await call.answer("Отзыв не найден", show_alert=True)

    except Exception as e:
        log.error("send_error", extra={"rid": rid, "error": str(e)}, exc_info=True)
        with suppress(Exception):
            await call.answer("Ошибка отправки", show_alert=True)


def setup(dp: Dispatcher):
    """Register review handlers."""
    dp.register_message_handler(cmd_reviews, commands=["reviews", "r"])
    dp.register_callback_query_handler(cb_draft, lambda c: c.data.startswith("rev_draft:"))
    dp.register_callback_query_handler(cb_send, lambda c: c.data.startswith("rev_send:"))
