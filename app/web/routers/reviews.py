"""Reviews API endpoints."""

from __future__ import annotations

from datetime import timezone, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update

from app.db.models import Review
from app.services.reviews_service import build_reply_for_review
from app.services.reviews_sla import update_first_reply_timestamp
from app.web.deps import CurrentUser, DBSession, OrgScope, require_admin
from app.web.schemas import ReplyRequest, ReviewDTO

router = APIRouter()


@router.get("", response_model=list[ReviewDTO])
def get_reviews(
    org_id: OrgScope,
    db: DBSession,
    user: CurrentUser,
    status: str | None = Query(None, description="Filter by reply_status: pending|sent"),
    marketplace: str | None = Query(
        None, pattern="^(WB|OZON)$", description="Filter by marketplace"
    ),
    rating: int | None = Query(None, ge=1, le=5, description="Filter by rating"),
    limit: int = Query(50, ge=1, le=200, description="Max reviews to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order by created_at"),
) -> list[ReviewDTO]:
    """Get reviews list with optional filtering.

    Filters:
    - status: 'pending' (no reply) or 'sent' (replied)
    - marketplace: 'WB' or 'OZON'
    - rating: 1-5 stars
    - order: 'asc' or 'desc' by created_at_utc
    """
    stmt = select(Review).where(Review.org_id == org_id)

    # Apply filters
    if status == "pending":
        stmt = stmt.where(Review.answer.is_(None))
    elif status == "sent":
        stmt = stmt.where(Review.answered == True)

    if rating is not None:
        stmt = stmt.where(Review.rating == rating)

    # Apply ordering
    if order == "desc":
        stmt = stmt.order_by(Review.created_at_utc.desc())
    else:
        stmt = stmt.order_by(Review.created_at_utc.asc())

    stmt = stmt.offset(offset).limit(limit)

    results = db.execute(stmt).scalars().all()

    return [
        ReviewDTO(
            review_id=r.id,
            marketplace="WB",  # Default since old schema doesn't have this field
            sku_key=r.sku,
            rating=r.rating,
            text=r.text,
            created_at_utc=r.created_at_utc.isoformat() if r.created_at_utc else (r.date.isoformat() if r.date else None),
            reply_status="sent" if r.answered else None,
            reply_text=r.reply_text,
        )
        for r in results
    ]


@router.post("/{review_id}/draft")
async def generate_reply_draft(
    review_id: str,
    org_id: OrgScope,
    db: DBSession,
    user: CurrentUser,
) -> dict:
    """Generate reply draft using Answer Engine (Stage 12).

    Returns generated reply text WITHOUT marking review as sent.
    Uses classification (typical/atypical) and templates/AI accordingly.

    Args:
        review_id: Review identifier
        org_id: Organization ID (auto-injected)
        db: Database session
        user: Current user (authenticated)

    Returns:
        Dict with review_id, draft_text, classification

    """
    try:
        # Generate reply using Answer Engine
        draft_text = await build_reply_for_review(review_id, db)

        # Get review for classification info (scoped to org)
        stmt = select(Review).where(Review.id == review_id, Review.org_id == org_id)
        review = db.execute(stmt).scalar_one_or_none()

        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        return {
            "review_id": review_id,
            "draft_text": draft_text,
            "rating": review.rating,
            "has_media": review.has_media or False,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate draft: {e!s}")


@router.post("/{review_id}/reply")
def post_review_reply(
    review_id: str,
    payload: ReplyRequest,
    org_id: OrgScope,
    db: DBSession,
    user: dict = Depends(require_admin),
) -> dict:
    """Post reply to a review.

    Marks review as 'sent' and stores reply text.
    Future: Will post to marketplace API when available.
    """
    # Find review (scoped to org)
    stmt = select(Review).where(Review.id == review_id, Review.org_id == org_id)
    review = db.execute(stmt).scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review.answered:
        raise HTTPException(status_code=400, detail="Review already replied")

    # Determine reply_kind based on text characteristics
    # If user provides custom text, it's likely edited/AI-assisted
    # For now, we'll infer: if text matches common templates, mark as 'template', else 'ai'
    reply_kind = "ai"  # Default assumption: custom/AI-assisted

    # Simple heuristic: if text is very short (<50 chars), likely template
    if len(payload.text) < 50:
        reply_kind = "template"

    # Update review
    now_utc = datetime.now(timezone.utc)
    db.execute(
        update(Review)
        .where(Review.id == review_id)
        .values(
            answered=True,
            answer=payload.text,
            reply_text=payload.text,
            first_reply_at_utc=now_utc,
            reply_kind=reply_kind,
        )
    )
    db.commit()

    # Track TTFR for SLA (Stage 18)
    update_first_reply_timestamp(db, review.id, when=now_utc, reply_kind=reply_kind)

    # TODO: Post to WB/Ozon API when available
    # await post_reply_to_marketplace(review, payload.text)

    return {"status": "ok", "review_id": review_id, "message": "Reply marked as sent"}
