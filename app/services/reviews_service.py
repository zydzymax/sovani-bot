"""Reviews service for E2E review management."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai.replies import generate_custom_reply
from app.core.metrics import reviews_processed_total
from app.db.models import Review
from app.domain.reviews.classifier import classify_review
from app.domain.reviews.templates import choose_template, personalize_reply

log = logging.getLogger(__name__)


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


async def build_reply_for_review(review_id: str, db: Session) -> str:
    """Build reply for review using Answer Engine (Stage 12).

    Steps:
        1. Fetch Review from database
        2. Classify review (typical vs atypical)
        3. If typical → choose template and personalize
           If atypical → generate custom AI reply
        4. Return reply text (does not mark as sent)

    Args:
        review_id: Review identifier
        db: Database session

    Returns:
        Generated reply text

    Raises:
        ValueError: If review not found

    """
    # 1. Fetch review
    stmt = select(Review).where(Review.review_id == review_id)
    review = db.execute(stmt).scalar_one_or_none()

    if not review:
        raise ValueError(f"Review not found: {review_id}")

    # Extract review data
    rating = review.rating
    text = review.text or ""
    has_media = review.has_media or False
    # TODO: Extract name from customer profile if available
    name = None  # For now, no name extraction

    # 2. Classify review
    classification = classify_review(rating=rating, text=text, has_media=has_media)

    log.info(
        f"Review classified: {review_id} → {classification} "
        f"(rating={rating}, text_len={len(text)}, has_media={has_media})"
    )

    # 3. Generate reply based on classification
    if classification in {"typical_positive", "typical_negative", "typical_neutral"}:
        # Use template
        template = choose_template(classification)
        reply_text = personalize_reply(name=name, template=template)
        reply_type = "template"

        log.info(f"Using template for {review_id}: {classification}")

    else:  # atypical
        # Use AI
        reply_text = await generate_custom_reply(
            name=name,
            rating=rating,
            text=text,
            has_media=has_media,
        )
        reply_type = "custom_ai"

        log.info(f"Using AI for {review_id}: rating={rating}, text_len={len(text)}")

    # Update metrics
    marketplace = review.marketplace or "unknown"
    reviews_processed_total.labels(
        marketplace=marketplace,
        status=reply_type,  # template or custom_ai
    ).inc()

    return reply_text


async def generate_reply_for_review(review: Review) -> str:
    """Generate AI reply for a review (legacy compatibility).

    DEPRECATED: Use build_reply_for_review() instead.

    Args:
        review: Review object

    Returns:
        Generated reply text

    """
    # Fallback to new Answer Engine
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return await build_reply_for_review(review.review_id, db)
    finally:
        db.close()


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
