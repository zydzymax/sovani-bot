"""FastAPI dependencies for authentication and database."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.web.auth import validate_init_data


def get_db() -> Session:
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(x_telegram_init_data: Annotated[str | None, Header()] = None) -> dict:
    """Validate Telegram WebApp user.

    Args:
        x_telegram_init_data: Telegram initData from header

    Returns:
        Dict with user info (id, is_admin)

    Raises:
        HTTPException: If authentication fails

    """
    settings = get_settings()

    # DEV_MODE bypass for local development
    dev_mode = settings.timezone == "DEV_MODE"  # Hack: reuse timezone field
    if dev_mode:
        return {"id": "dev", "username": "developer", "is_admin": True}

    # Require initData in production
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")

    # Validate signature
    try:
        data = validate_init_data(x_telegram_init_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid initData: {e}")

    # Parse user info
    user_json = data.get("user", "{}")
    try:
        user_info = json.loads(user_json)
        user_id = str(user_info.get("id", ""))
        username = user_info.get("username", "")
    except (json.JSONDecodeError, AttributeError):
        raise HTTPException(status_code=401, detail="Invalid user data in initData")

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user ID in initData")

    # Check allowlist (optional - you can add ALLOWED_TG_USER_IDS env var)
    # allowed_ids = settings.manager_chat_id  # or separate allowlist
    # if user_id not in allowed_ids:
    #     raise HTTPException(status_code=403, detail="User not authorized")

    return {"id": user_id, "username": username, "is_admin": True}


# Type aliases for cleaner endpoints
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(current_user)]
