"""Development/debug endpoints - ONLY enabled in DEV_MODE."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.web.deps import DBSession

router = APIRouter()


@router.get("/impersonate")
def dev_impersonate(
    db: DBSession,
    tg_id: int = Query(..., description="Telegram user ID to impersonate"),
) -> dict:
    """DEV ONLY: Impersonate a Telegram user for testing TMA.

    Creates/finds user, assigns to Default org as owner, returns user profile.

    Args:
        tg_id: Telegram user ID to impersonate
        db: Database session

    Returns:
        User profile with org context

    Raises:
        HTTPException 403: If DEV_MODE is not enabled

    """
    settings = get_settings()

    if not settings.dev_mode:
        raise HTTPException(status_code=403, detail="DEV mode not enabled")

    # Check if user exists
    user_row = db.execute(
        text("SELECT id FROM users WHERE tg_user_id = :tg_id"), {"tg_id": tg_id}
    ).first()

    if user_row:
        user_id = user_row[0]
    else:
        # Create user
        db.execute(
            text(
                """
                INSERT INTO users (tg_user_id, tg_username, tg_first_name)
                VALUES (:tg_id, :username, :first_name)
            """
            ),
            {"tg_id": tg_id, "username": f"dev_user_{tg_id}", "first_name": "DEV User"},
        )
        db.commit()
        user_id = db.execute(text("SELECT last_insert_rowid()")).scalar()

    # Check org membership
    membership_row = db.execute(
        text(
            """
            SELECT org_id, role
            FROM org_members
            WHERE user_id = :user_id
            LIMIT 1
        """
        ),
        {"user_id": user_id},
    ).first()

    if membership_row:
        org_id, role = membership_row
    else:
        # Get or create default org
        default_org_row = db.execute(
            text("SELECT id FROM organizations WHERE name = :name"),
            {"name": settings.default_org_name},
        ).first()

        if not default_org_row:
            db.execute(
                text("INSERT INTO organizations (name) VALUES (:name)"),
                {"name": settings.default_org_name},
            )
            db.commit()
            org_id = db.execute(text("SELECT last_insert_rowid()")).scalar()
        else:
            org_id = default_org_row[0]

        # Add as owner
        role = "owner"
        db.execute(
            text(
                """
                INSERT INTO org_members (org_id, user_id, role)
                VALUES (:org_id, :user_id, :role)
            """
            ),
            {"org_id": org_id, "user_id": user_id, "role": role},
        )
        db.commit()

    return {
        "user_id": user_id,
        "tg_user_id": tg_id,
        "org_id": org_id,
        "role": role,
        "dev_mode": True,
        "message": "User created/found and assigned to Default org",
    }
