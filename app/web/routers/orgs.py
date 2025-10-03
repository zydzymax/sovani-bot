"""Organizations management API (Stage 19).

Endpoints:
- GET /api/v1/orgs/me - Current user's orgs
- POST /api/v1/orgs - Create org
- GET /api/v1/orgs/{org_id}/members - List members
- POST /api/v1/orgs/{org_id}/invite - Invite member
- PATCH /api/v1/orgs/{org_id}/members/{user_id} - Change role
- DELETE /api/v1/orgs/{org_id}/members/{user_id} - Remove member
- GET /api/v1/orgs/{org_id}/credentials - Get credentials (masked)
- PATCH /api/v1/orgs/{org_id}/credentials - Update credentials
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.orgs import (
    change_member_role,
    create_organization,
    get_credentials,
    get_user_organizations,
    invite_member,
    list_members,
    remove_member,
    update_credentials,
)
from app.web.auth import CurrentUser, get_current_user, require_org_member

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orgs")


# === Request/Response Models ===


class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class InviteMemberRequest(BaseModel):
    tg_user_id: int
    role: str = Field(..., pattern="^(owner|manager|viewer)$")


class ChangeMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(owner|manager|viewer)$")


class UpdateCredentialsRequest(BaseModel):
    wb_feedbacks_token: str | None = None
    wb_ads_token: str | None = None
    wb_stats_token: str | None = None
    wb_supply_token: str | None = None
    wb_analytics_token: str | None = None
    wb_content_token: str | None = None
    ozon_client_id: str | None = None
    ozon_api_key_admin: str | None = None


# === Endpoints ===


@router.get("/me")
async def get_my_orgs(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get current user's organizations and active org.

    Returns:
        Dict with current_org and all orgs list

    """
    orgs = get_user_organizations(db, current_user.user_id)

    # Find current org details
    current_org = next(
        (org for org in orgs if org["org_id"] == current_user.org_id),
        None,
    )

    return {
        "current_org": current_org,
        "organizations": orgs,
    }


@router.post("")
async def create_org(
    payload: CreateOrgRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create new organization (creator becomes owner).

    Args:
        payload: Organization name

    Returns:
        Dict with org_id and name

    """
    try:
        org = create_organization(db, payload.name, current_user.user_id)
        return org
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{org_id}/members")
async def get_org_members(
    org_id: int,
    current_user: CurrentUser = Depends(require_org_member("viewer")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List organization members.

    Args:
        org_id: Organization ID

    Returns:
        Dict with members list

    """
    # Ensure user is querying their own org
    if current_user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied to other organization")

    members = list_members(db, org_id)
    return {"members": members}


@router.post("/{org_id}/invite")
async def invite_org_member(
    org_id: int,
    payload: InviteMemberRequest,
    current_user: CurrentUser = Depends(require_org_member("owner")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Invite user to organization (owner only).

    Args:
        org_id: Organization ID
        payload: User tg_user_id and role

    Returns:
        Dict with invited user_id and role

    """
    # Ensure user is inviting to their own org
    if current_user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Can only invite to your own organization")

    try:
        result = invite_member(db, org_id, payload.tg_user_id, payload.role, current_user.user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{org_id}/members/{user_id}")
async def change_org_member_role(
    org_id: int,
    user_id: int,
    payload: ChangeMemberRoleRequest,
    current_user: CurrentUser = Depends(require_org_member("owner")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Change member role (owner only).

    Args:
        org_id: Organization ID
        user_id: User ID to update
        payload: New role

    Returns:
        Dict with updated user_id and role

    """
    # Ensure user is updating their own org
    if current_user.org_id != org_id:
        raise HTTPException(
            status_code=403, detail="Can only update members in your own organization"
        )

    try:
        result = change_member_role(db, org_id, user_id, payload.role, current_user.user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{org_id}/members/{user_id}")
async def remove_org_member(
    org_id: int,
    user_id: int,
    current_user: CurrentUser = Depends(require_org_member("owner")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Remove member from organization (owner only).

    Args:
        org_id: Organization ID
        user_id: User ID to remove

    Returns:
        Success message

    """
    # Ensure user is removing from their own org
    if current_user.org_id != org_id:
        raise HTTPException(
            status_code=403, detail="Can only remove members from your own organization"
        )

    # Prevent self-removal
    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    try:
        remove_member(db, org_id, user_id, current_user.user_id)
        return {"status": "removed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{org_id}/credentials")
async def get_org_credentials(
    org_id: int,
    current_user: CurrentUser = Depends(require_org_member("owner")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get organization credentials (owner only, masked).

    Args:
        org_id: Organization ID

    Returns:
        Dict with masked credentials

    """
    # Ensure user is querying their own org
    if current_user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied to other organization")

    creds = get_credentials(db, org_id)

    # Mask tokens (show only last 8 chars)
    masked_creds = {}
    for key, value in creds.items():
        if value:
            if len(value) > 8:
                masked_creds[key] = "..." + value[-8:]
            else:
                masked_creds[key] = "***"
        else:
            masked_creds[key] = None

    return masked_creds


@router.patch("/{org_id}/credentials")
async def update_org_credentials(
    org_id: int,
    payload: UpdateCredentialsRequest,
    current_user: CurrentUser = Depends(require_org_member("owner")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Update organization credentials (owner only).

    Args:
        org_id: Organization ID
        payload: Credentials to update

    Returns:
        Success message

    """
    # Ensure user is updating their own org
    if current_user.org_id != org_id:
        raise HTTPException(
            status_code=403, detail="Can only update credentials for your own organization"
        )

    # Filter out None values (only update provided fields)
    creds_dict = payload.dict(exclude_none=True)

    if not creds_dict:
        raise HTTPException(status_code=400, detail="No credentials provided")

    update_credentials(db, org_id, creds_dict, current_user.user_id)

    return {"status": "updated"}
