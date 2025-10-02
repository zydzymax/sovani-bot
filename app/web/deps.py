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
    """Validate Telegram WebApp user with RBAC.

    Args:
        x_telegram_init_data: Telegram initData from header

    Returns:
        Dict with user info (id, username, role)

    Raises:
        HTTPException: If authentication fails

    """
    settings = get_settings()

    # DEV_MODE bypass for local development
    dev_mode = settings.timezone == "DEV_MODE"  # Hack: reuse timezone field
    if dev_mode:
        return {"id": "dev", "username": "developer", "role": "admin"}

    # Require initData in production
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")

    # Validate signature
    try:
        data = validate_init_data(x_telegram_init_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid initData: {e}") from e

    # Parse user info
    user_json = data.get("user", "{}")
    try:
        user_info = json.loads(user_json)
        user_id = str(user_info.get("id", ""))
        username = user_info.get("username", "")
    except (json.JSONDecodeError, AttributeError) as e:
        raise HTTPException(status_code=401, detail="Invalid user data in initData") from e

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user ID in initData")

    # Determine role from allowlists
    admin_ids = settings.admin_user_ids
    viewer_ids = settings.viewer_user_ids

    if user_id in admin_ids:
        role = "admin"
    elif user_id in viewer_ids:
        role = "viewer"
    else:
        raise HTTPException(status_code=403, detail="User not authorized")

    return {"id": user_id, "username": username, "role": role}


def require_admin(user: dict = Depends(current_user)) -> dict:
    """Require admin role.

    Args:
        user: Current user from current_user dependency

    Returns:
        User dict if admin

    Raises:
        HTTPException: If user is not admin

    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


# Type aliases for cleaner endpoints
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(current_user)]
