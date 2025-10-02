"""Telegram handlers for review management."""

from __future__ import annotations

from aiogram import Dispatcher, types

from app.db.session import SessionLocal
from app.services.reviews_service import (
    fetch_pending_reviews,
    generate_reply_for_review,
    mark_reply_sent,
    post_reply,
)


async def cmd_reviews(message: types.Message):
    """Handle /reviews command - show pending reviews."""
    with SessionLocal() as db:
        reviews = await fetch_pending_reviews(db, limit=10)

    if not reviews:
        return await message.answer("Новых отзывов нет ✅")

    for review in reviews:
        text = review.text or "(без текста)"
        truncated = text[:400] + "…" if len(text) > 400 else text

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(
                "Сгенерировать ответ", callback_data=f"rev_gen:{review.review_id}"
            )
        )

        await message.answer(
            f"⭐{review.rating or '?'} | {review.marketplace or 'N/A'} | {review.sku_key or 'N/A'}\n\n{truncated}",
            reply_markup=kb,
        )


async def cb_generate_reply(call: types.CallbackQuery):
    """Handle callback for generating review reply."""
    _, rid = call.data.split(":", 1)

    # Fetch review by ID
    with SessionLocal() as db:
        reviews = await fetch_pending_reviews(db, limit=100)
        review = next((x for x in reviews if x.review_id == rid), None)

        if not review:
            return await call.answer("Отзыв не найден", show_alert=True)

        # Generate reply
        reply_text = await generate_reply_for_review(review)

        # Post reply (stub - just marks as ready)
        sent = await post_reply(review, reply_text)

        if sent:
            await mark_reply_sent(db, review.review_id, reply_text)
            await call.message.answer(
                f"✅ Ответ сгенерирован и отмечен как отправленный:\n\n{reply_text}"
            )
        else:
            await call.message.answer(f"⚠️ Не удалось отправить ответ:\n\n{reply_text}")

    await call.answer()


def setup(dp: Dispatcher):
    """Register review handlers."""
    dp.register_message_handler(cmd_reviews, commands=["reviews", "r"])
    dp.register_callback_query_handler(cb_generate_reply, lambda c: c.data.startswith("rev_gen:"))
