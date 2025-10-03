"""Organizations management service (Stage 19).

Handles:
- Organization CRUD
- Member management (invite, remove, change role)
- Credentials management
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.credentials import decrypt_credentials, encrypt_credentials

logger = logging.getLogger(__name__)


def create_organization(db: Session, name: str, creator_user_id: int) -> dict[str, Any]:
    """Create new organization with creator as owner.

    Args:
        db: Database session
        name: Organization name
        creator_user_id: User ID of creator

    Returns:
        Dict with org_id and name

    Raises:
        ValueError: If org name already exists

    """
    # Check if name exists
    existing = db.execute(
        text("SELECT id FROM organizations WHERE name = :name"),
        {"name": name},
    ).first()

    if existing:
        raise ValueError(f"Organization '{name}' already exists")

    # Create org
    db.execute(
        text("INSERT INTO organizations (name) VALUES (:name)"),
        {"name": name},
    )
    db.commit()

    org_id = db.execute(text("SELECT last_insert_rowid()")).scalar()

    # Add creator as owner
    db.execute(
        text(
            """
            INSERT INTO org_members (org_id, user_id, role)
            VALUES (:org_id, :user_id, 'owner')
        """
        ),
        {"org_id": org_id, "user_id": creator_user_id},
    )
    db.commit()

    logger.info(f"Created org {org_id} '{name}' with owner user_id={creator_user_id}")

    return {"org_id": org_id, "name": name}


def invite_member(
    db: Session,
    org_id: int,
    tg_user_id: int,
    role: str,
    inviter_user_id: int,
) -> dict[str, Any]:
    """Invite user to organization.

    Args:
        db: Database session
        org_id: Organization ID
        tg_user_id: Telegram user ID to invite
        role: Role to assign (owner|manager|viewer)
        inviter_user_id: User ID performing the invite (for audit)

    Returns:
        Dict with user_id and role

    Raises:
        ValueError: If user not found or role invalid

    """
    if role not in ("owner", "manager", "viewer"):
        raise ValueError(f"Invalid role: {role}")

    # Get user_id from tg_user_id
    user_row = db.execute(
        text("SELECT id FROM users WHERE tg_user_id = :tg_user_id"),
        {"tg_user_id": tg_user_id},
    ).first()

    if not user_row:
        raise ValueError(f"User with tg_user_id={tg_user_id} not found")

    user_id = user_row[0]

    # Check if already member
    existing = db.execute(
        text(
            """
            SELECT role FROM org_members
            WHERE org_id = :org_id AND user_id = :user_id
        """
        ),
        {"org_id": org_id, "user_id": user_id},
    ).first()

    if existing:
        raise ValueError(
            f"User {user_id} is already member of org {org_id} with role {existing[0]}"
        )

    # Add member
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

    logger.info(
        f"Added user {user_id} to org {org_id} with role {role} (inviter={inviter_user_id})"
    )

    return {"user_id": user_id, "role": role}


def change_member_role(
    db: Session,
    org_id: int,
    user_id: int,
    new_role: str,
    changer_user_id: int,
) -> dict[str, Any]:
    """Change member's role in organization.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID to update
        new_role: New role (owner|manager|viewer)
        changer_user_id: User ID performing the change (for audit)

    Returns:
        Dict with updated role

    Raises:
        ValueError: If user not member or role invalid

    """
    if new_role not in ("owner", "manager", "viewer"):
        raise ValueError(f"Invalid role: {new_role}")

    # Check if member exists
    existing = db.execute(
        text(
            """
            SELECT role FROM org_members
            WHERE org_id = :org_id AND user_id = :user_id
        """
        ),
        {"org_id": org_id, "user_id": user_id},
    ).first()

    if not existing:
        raise ValueError(f"User {user_id} is not member of org {org_id}")

    # Update role
    db.execute(
        text(
            """
            UPDATE org_members
            SET role = :new_role
            WHERE org_id = :org_id AND user_id = :user_id
        """
        ),
        {"org_id": org_id, "user_id": user_id, "new_role": new_role},
    )
    db.commit()

    logger.info(
        f"Changed user {user_id} role in org {org_id} from {existing[0]} to {new_role} (by user {changer_user_id})"
    )

    return {"user_id": user_id, "role": new_role}


def remove_member(
    db: Session,
    org_id: int,
    user_id: int,
    remover_user_id: int,
) -> None:
    """Remove member from organization.

    Args:
        db: Database session
        org_id: Organization ID
        user_id: User ID to remove
        remover_user_id: User ID performing the removal (for audit)

    Raises:
        ValueError: If user not member or last owner

    """
    # Check if member exists
    existing = db.execute(
        text(
            """
            SELECT role FROM org_members
            WHERE org_id = :org_id AND user_id = :user_id
        """
        ),
        {"org_id": org_id, "user_id": user_id},
    ).first()

    if not existing:
        raise ValueError(f"User {user_id} is not member of org {org_id}")

    # Prevent removing last owner
    if existing[0] == "owner":
        owner_count = db.execute(
            text(
                """
                SELECT COUNT(*) FROM org_members
                WHERE org_id = :org_id AND role = 'owner'
            """
            ),
            {"org_id": org_id},
        ).scalar()

        if owner_count <= 1:
            raise ValueError("Cannot remove last owner of organization")

    # Remove member
    db.execute(
        text(
            """
            DELETE FROM org_members
            WHERE org_id = :org_id AND user_id = :user_id
        """
        ),
        {"org_id": org_id, "user_id": user_id},
    )
    db.commit()

    logger.info(f"Removed user {user_id} from org {org_id} (by user {remover_user_id})")


def list_members(db: Session, org_id: int) -> list[dict[str, Any]]:
    """List all members of organization.

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        List of member dicts with user info and role

    """
    rows = db.execute(
        text(
            """
            SELECT
                u.id AS user_id,
                u.tg_user_id,
                u.tg_username,
                u.tg_first_name,
                u.tg_last_name,
                om.role,
                om.created_at
            FROM org_members om
            JOIN users u ON u.id = om.user_id
            WHERE om.org_id = :org_id
            ORDER BY om.created_at ASC
        """
        ),
        {"org_id": org_id},
    ).fetchall()

    return [
        {
            "user_id": row[0],
            "tg_user_id": row[1],
            "tg_username": row[2],
            "tg_first_name": row[3],
            "tg_last_name": row[4],
            "role": row[5],
            "joined_at": row[6].isoformat() if row[6] else None,
        }
        for row in rows
    ]


def get_user_organizations(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Get all organizations user belongs to.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        List of org dicts with role

    """
    rows = db.execute(
        text(
            """
            SELECT
                o.id AS org_id,
                o.name,
                om.role,
                o.created_at
            FROM org_members om
            JOIN organizations o ON o.id = om.org_id
            WHERE om.user_id = :user_id
            ORDER BY o.created_at ASC
        """
        ),
        {"user_id": user_id},
    ).fetchall()

    return [
        {
            "org_id": row[0],
            "name": row[1],
            "role": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
        }
        for row in rows
    ]


def update_credentials(
    db: Session,
    org_id: int,
    credentials: dict[str, str | None],
    updater_user_id: int,
) -> None:
    """Update marketplace credentials for organization.

    Args:
        db: Database session
        org_id: Organization ID
        credentials: Dict with credential keys (wb_feedbacks_token, etc.)
        updater_user_id: User ID performing the update (for audit)

    """
    # Encrypt sensitive fields before storage
    encrypted_creds = encrypt_credentials(credentials)

    # Build SET clause dynamically
    set_clauses = []
    params = {"org_id": org_id}

    for key, value in encrypted_creds.items():
        if key in (
            "wb_feedbacks_token",
            "wb_ads_token",
            "wb_stats_token",
            "wb_supply_token",
            "wb_analytics_token",
            "wb_content_token",
            "ozon_client_id",
            "ozon_api_key_admin",
        ):
            set_clauses.append(f"{key} = :{key}")
            params[key] = value

    if not set_clauses:
        return

    # Upsert credentials
    existing = db.execute(
        text("SELECT org_id FROM org_credentials WHERE org_id = :org_id"),
        {"org_id": org_id},
    ).first()

    if existing:
        # Update
        query = f"""
            UPDATE org_credentials
            SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
            WHERE org_id = :org_id
        """
    else:
        # Insert
        keys = list(params.keys())
        placeholders = [f":{k}" for k in keys]
        query = f"""
            INSERT INTO org_credentials ({', '.join(keys)}, updated_at)
            VALUES ({', '.join(placeholders)}, CURRENT_TIMESTAMP)
        """

    db.execute(text(query), params)
    db.commit()

    # Log without exposing tokens
    masked_creds = {k: "***" if v else None for k, v in credentials.items()}
    logger.info(f"Updated credentials for org {org_id}: {masked_creds} (by user {updater_user_id})")


def get_credentials(db: Session, org_id: int) -> dict[str, str | None]:
    """Get marketplace credentials for organization.

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        Dict with credentials (empty strings if not set)

    """
    row = db.execute(
        text(
            """
            SELECT
                wb_feedbacks_token,
                wb_ads_token,
                wb_stats_token,
                wb_supply_token,
                wb_analytics_token,
                wb_content_token,
                ozon_client_id,
                ozon_api_key_admin
            FROM org_credentials
            WHERE org_id = :org_id
        """
        ),
        {"org_id": org_id},
    ).first()

    if not row:
        return {
            "wb_feedbacks_token": None,
            "wb_ads_token": None,
            "wb_stats_token": None,
            "wb_supply_token": None,
            "wb_analytics_token": None,
            "wb_content_token": None,
            "ozon_client_id": None,
            "ozon_api_key_admin": None,
        }

    encrypted_creds = {
        "wb_feedbacks_token": row[0],
        "wb_ads_token": row[1],
        "wb_stats_token": row[2],
        "wb_supply_token": row[3],
        "wb_analytics_token": row[4],
        "wb_content_token": row[5],
        "ozon_client_id": row[6],
        "ozon_api_key_admin": row[7],
    }

    # Decrypt sensitive fields before returning
    return decrypt_credentials(encrypted_creds)
