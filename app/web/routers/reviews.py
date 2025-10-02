"""Reviews API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import select, update

from app.db.models import Review
from app.web.deps import CurrentUser, DBSession
from app.web.schemas import ReplyRequest, ReviewDTO

router = APIRouter()


@router.get("", response_model=list[ReviewDTO])
def get_reviews(
    db: DBSession,
    user: CurrentUser,
    status: str | None = Query(None, description="Filter by reply_status: pending|sent"),
    limit: int = Query(50, ge=1, le=200, description="Max reviews to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> list[ReviewDTO]:
    """Get reviews list with optional filtering.

    Status filter:
    - 'pending': Reviews without replies (reply_status IS NULL)
    - 'sent': Reviews with replies sent
    - None: All reviews
    """
    stmt = select(Review).order_by(Review.created_at_utc.desc())

    if status == "pending":
        stmt = stmt.where(Review.reply_status.is_(None))
    elif status == "sent":
        stmt = stmt.where(Review.reply_status == "sent")

    stmt = stmt.offset(offset).limit(limit)

    results = db.execute(stmt).scalars().all()

    return [
        ReviewDTO(
            review_id=r.review_id,
            marketplace=r.marketplace,
            sku_key=r.sku_key,
            rating=r.rating,
            text=r.text,
            created_at_utc=r.created_at_utc.isoformat() if r.created_at_utc else None,
            reply_status=r.reply_status,
            reply_text=r.reply_text,
        )
        for r in results
    ]


@router.post("/{review_id}/reply")
def post_review_reply(
    db: DBSession,
    user: CurrentUser,
    review_id: str = Path(..., description="Review ID"),
    payload: ReplyRequest = ...,
) -> dict:
    """Post reply to a review.

    Marks review as 'sent' and stores reply text.
    Future: Will post to marketplace API when available.
    """
    # Find review
    stmt = select(Review).where(Review.review_id == review_id)
    review = db.execute(stmt).scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.reply_status == "sent":
        raise HTTPException(status_code=400, detail="Review already replied")

    # Update review
    db.execute(
        update(Review)
        .where(Review.review_id == review_id)
        .values(
            reply_status="sent",
            reply_id="local",
            reply_text=payload.text,
            replied_at_utc=datetime.now(UTC),
        )
    )
    db.commit()

    # TODO: Post to WB/Ozon API when available
    # await post_reply_to_marketplace(review, payload.text)

    return {"status": "ok", "review_id": review_id, "message": "Reply marked as sent"}
