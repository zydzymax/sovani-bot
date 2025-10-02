"""Reviews service for E2E review management."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Review
from app.domain.reviews.reply_policy import build_reply_prompt

log = get_logger("sovani_bot.reviews")


async def fetch_pending_reviews(db: Session, limit: int = 50) -> list[Review]:
    """Fetch reviews without replies (reply_status IS NULL).

    Args:
        db: Database session
        limit: Maximum number of reviews to fetch

    Returns:
        List of pending reviews

    """
    stmt = (
        select(Review)
        .where(Review.reply_status.is_(None))
        .order_by(Review.created_at_utc.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


async def generate_reply_for_review(review: Review) -> str:
    """Generate AI reply for a review using existing ai_reply module.

    Args:
        review: Review object

    Returns:
        Generated reply text

    """
    # Import legacy ai_reply module
    try:
        import os
        import sys

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from ai_reply import generate_review_reply

        # Convert Review model to dict format expected by legacy module
        review_dict = {
            "text": review.text or "",
            "rating": review.rating or 3,
            "has_media": False,  # TODO: Add media detection
            "platform": "WB" if "WB" in (review.marketplace or "").upper() else "OZON",
            "sku": review.sku_key or "N/A",
        }

        return await generate_review_reply(review_dict)

    except Exception as e:
        log.error("ai_reply_failed", extra={"review_id": review.review_id, "error": str(e)})
        # Fallback: use simple policy-based reply
        prompt = build_reply_prompt(review.rating or 3, review.text or "")
        return f"Спасибо за отзыв! {prompt[:100]}..."


async def mark_reply_sent(db: Session, review_id: str, reply_text: str) -> None:
    """Mark review as replied with generated text.

    Args:
        db: Database session
        review_id: Review identifier
        reply_text: Generated reply text

    """
    db.execute(
        update(Review)
        .where(Review.review_id == review_id)
        .values(
            reply_status="sent",
            reply_id="local",
            replied_at_utc=datetime.now(UTC),
            reply_text=reply_text,
        )
    )
    db.commit()


async def post_reply(review: Review, reply_text: str) -> bool:
    """Post reply to marketplace (stub - WB/Ozon don't have public API for this).

    Args:
        review: Review object
        reply_text: Reply text to post

    Returns:
        True if successful (always True in stub)

    """
    # TODO: Implement actual posting when WB/Ozon provide API
    # For now, we just log and mark as ready for manual posting
    log.info("reply_ready", extra={"review_id": review.review_id, "len": len(reply_text)})
    return True
