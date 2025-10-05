"""Multi-tenant authentication with Telegram WebApp (Stage 19).

Handles:
- Telegram WebApp initData validation
- User auto-creation and org membership
- Current user context (org_id, role)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db

logger = logging.getLogger(__name__)
log = get_logger("sovani_bot.auth")


class CurrentUser:
    """Current authenticated user with org context."""

    def __init__(
        self,
        user_id: int,
        tg_user_id: int,
        org_id: int,
        role: str,
        tg_username: str | None = None,
        tg_first_name: str | None = None,
    ):
        self.user_id = user_id
        self.tg_user_id = tg_user_id
        self.org_id = org_id
        self.role = role  # owner | manager | viewer
        self.tg_username = tg_username
        self.tg_first_name = tg_first_name

    def __repr__(self) -> str:
        return f"<CurrentUser user_id={self.user_id} org_id={self.org_id} role={self.role}>"


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    """Validate Telegram WebApp initData signature.

    Args:
        init_data: URL-encoded initData from Telegram WebApp
        bot_token: Bot token for signature verification

    Returns:
        Parsed data dict if valid, None otherwise

    """
    try:
        # Parse init_data
        parsed = dict(parse_qsl(init_data))
        hash_value = parsed.pop("hash", None)

        if not hash_value:
            return None

        # Build data-check-string
        data_check_arr = [f"{k}={v}" for k, v in sorted(parsed.items())]
        data_check_string = "\n".join(data_check_arr)

        # Compute secret key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256,
        ).digest()

        # Compute hash
        computed_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if computed_hash != hash_value:
            logger.warning("Invalid Telegram initData signature")
            return None

        return parsed

    except Exception as e:
        logger.error(f"Failed to validate Telegram initData: {e}")
        return None


def get_or_create_user(
    db: Session, tg_user_id: int, user_data: dict[str, Any]
) -> tuple[int, int, str]:
    """Get or create user and assign to default org if needed.

    Args:
        db: Database session
        tg_user_id: Telegram user ID
        user_data: Parsed Telegram user data

    Returns:
        Tuple of (user_id, org_id, role)

    """
    settings = get_settings()

    # Check if user exists
    user_row = db.execute(
        text("SELECT id FROM users WHERE tg_user_id = :tg_user_id"),
        {"tg_user_id": tg_user_id},
    ).first()

    if user_row:
        user_id = user_row[0]
    else:
        # Create new user
        result = db.execute(
            text(
                """
                INSERT INTO users (tg_user_id, tg_username, tg_first_name, tg_last_name)
                VALUES (:tg_user_id, :username, :first_name, :last_name)
            """
            ),
            {
                "tg_user_id": tg_user_id,
                "username": user_data.get("username"),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            },
        )
        db.commit()

        # Get last inserted ID
        user_id = db.execute(text("SELECT last_insert_rowid()")).scalar()
        logger.info(f"Created new user {user_id} for tg_user_id={tg_user_id}")

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
        # Auto-assign to default org
        default_org_row = db.execute(
            text("SELECT id FROM organizations WHERE name = :name"),
            {"name": settings.default_org_name},
        ).first()

        if not default_org_row:
            # Create default org if doesn't exist
            db.execute(
                text("INSERT INTO organizations (name) VALUES (:name)"),
                {"name": settings.default_org_name},
            )
            db.commit()
            default_org_id = db.execute(text("SELECT last_insert_rowid()")).scalar()
        else:
            default_org_id = default_org_row[0]

        # Add user to default org as owner (first user) or manager
        role = "owner"  # First user in default org becomes owner
        db.execute(
            text(
                """
                INSERT INTO org_members (org_id, user_id, role)
                VALUES (:org_id, :user_id, :role)
            """
            ),
            {"org_id": default_org_id, "user_id": user_id, "role": role},
        )
        db.commit()

        org_id = default_org_id
        logger.info(f"Added user {user_id} to org {org_id} as {role}")

    return user_id, org_id, role


async def get_current_user(
    authorization: str | None = Header(None),
    x_telegram_init_data: str | None = Header(None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Get current authenticated user from Telegram WebApp initData.

    Supports two auth methods:
    1. X-Telegram-Init-Data header (Telegram WebApp)
    2. Authorization header with Telegram user ID (legacy/testing)

    Args:
        authorization: Optional Authorization header
        x_telegram_init_data: Optional Telegram initData header
        db: Database session

    Returns:
        CurrentUser with org context

    Raises:
        HTTPException: If authentication fails

    """
    settings = get_settings()

    # DEV_MODE bypass for local development
    dev_mode = settings.app_timezone == "DEV_MODE"
    if dev_mode:
        # Get default org ID
        default_org_row = db.execute(
            text("SELECT id FROM organizations LIMIT 1")
        ).first()
        org_id = default_org_row[0] if default_org_row else 1

        return CurrentUser(
            user_id=999,
            tg_user_id=999,
            org_id=org_id,
            role="owner",
            tg_username="developer",
            tg_first_name="Dev"
        )

    # Method 1: Telegram WebApp initData (production)
    if x_telegram_init_data:
        try:
            parsed_data = validate_telegram_init_data(x_telegram_init_data, settings.telegram_token)
        except ValueError as e:
            log.warning(
                "invalid_telegram_init_data",
                extra={"reason": "signature_mismatch", "error": str(e)},
            )
            raise HTTPException(
                status_code=401,
                detail={"error": "invalid_init_data", "reason": "signature_mismatch"},
            )

        if not parsed_data:
            log.warning("invalid_telegram_init_data", extra={"reason": "parse_failed"})
            raise HTTPException(
                status_code=401,
                detail={"error": "invalid_init_data", "reason": "parse_failed"},
            )

        # Extract user data
        user_data = json.loads(parsed_data.get("user", "{}"))
        tg_user_id = user_data.get("id")

        if not tg_user_id:
            log.warning("missing_telegram_user_id", extra={"user_data": user_data})
            raise HTTPException(
                status_code=401,
                detail={"error": "invalid_init_data", "reason": "missing_user_id"},
            )

        user_id, org_id, role = get_or_create_user(db, tg_user_id, user_data)

        return CurrentUser(
            user_id=user_id,
            tg_user_id=tg_user_id,
            org_id=org_id,
            role=role,
            tg_username=user_data.get("username"),
            tg_first_name=user_data.get("first_name"),
        )

    # Method 2: Legacy Authorization header (testing/CLI)
    elif authorization:
        # Format: "Bearer tg:<tg_user_id>"
        if not authorization.startswith("Bearer tg:"):
            raise HTTPException(status_code=401, detail="Invalid authorization format")

        try:
            tg_user_id = int(authorization.replace("Bearer tg:", ""))
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid Telegram user ID")

        # Get or create user
        user_data = {"id": tg_user_id, "username": None, "first_name": None, "last_name": None}
        user_id, org_id, role = get_or_create_user(db, tg_user_id, user_data)

        return CurrentUser(
            user_id=user_id,
            tg_user_id=tg_user_id,
            org_id=org_id,
            role=role,
        )

    else:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication (X-Telegram-Init-Data or Authorization header required)",
        )


def require_org_member(min_role: str = "viewer"):
    """Dependency to enforce org membership with minimum role.

    Args:
        min_role: Minimum required role (viewer|manager|owner)

    Returns:
        Dependency that returns CurrentUser if authorized

    Raises:
        HTTPException: If user doesn't have required role

    """
    role_hierarchy = {"viewer": 0, "manager": 1, "owner": 2}

    async def check_role(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        user_level = role_hierarchy.get(current_user.role, -1)
        required_level = role_hierarchy.get(min_role, 999)

        if user_level < required_level:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions: {min_role} role required",
            )

        return current_user

    return check_role


def get_org_scope(current_user: CurrentUser = Depends(get_current_user)) -> int:
    """Get org_id for scoping queries.

    Args:
        current_user: Current authenticated user

    Returns:
        Organization ID for filtering

    """
    return current_user.org_id
