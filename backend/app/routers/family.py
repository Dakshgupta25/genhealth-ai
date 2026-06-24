"""
Family router.

Endpoints:
  GET    /members              - List all family members
  POST   /members              - Add a family member
  PATCH  /members/:id          - Update a family member
  DELETE /members/:id          - Remove a family member
  POST   /invite               - Send invite to family member
  GET    /tree                 - Full family tree structure
  GET    /shared-risks         - Hereditary disease patterns
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db, get_redis
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.common import ok, err
from app.schemas.family import (
    FamilyInviteCreate,
    FamilyInviteOut,
    FamilyMemberCreate,
    FamilyMemberOut,
    FamilyMemberUpdate,
    FamilyTreeOut,
    HereditaryPatternsOut,
)
from app.services import family_service
from app.services.notification_service import send_invite_email
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/members", summary="List all family members")
async def list_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all family members in the authenticated user's health tree."""
    members = await family_service.list_family_members(current_user.id, db)
    return ok(
        data=[FamilyMemberOut.model_validate(m).model_dump() for m in members],
        message=f"{len(members)} family member(s) found.",
    )


@router.post("/members", status_code=status.HTTP_201_CREATED, summary="Add a family member")
async def add_member(
    data: FamilyMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a new family member to the authenticated user's health tree.

    The member is not linked to a platform account until an invite is sent and accepted.
    """
    member = await family_service.add_family_member(current_user.id, data, db)
    return ok(
        data=FamilyMemberOut.model_validate(member).model_dump(),
        message="Family member added successfully.",
    )


@router.patch("/members/{member_id}", summary="Update a family member")
async def update_member(
    member_id: UUID,
    data: FamilyMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Partially update a family member's information."""
    member = await family_service.get_family_member(member_id, current_user.id, db)
    if not member:
        raise HTTPException(status_code=404, detail=err("Family member not found.", "NOT_FOUND"))

    updated = await family_service.update_family_member(member, data, db)
    return ok(
        data=FamilyMemberOut.model_validate(updated).model_dump(),
        message="Family member updated.",
    )


@router.delete("/members/{member_id}", summary="Remove a family member")
async def delete_member(
    member_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a family member from the health tree.

    This also deletes all health records associated with that family member.
    """
    member = await family_service.get_family_member(member_id, current_user.id, db)
    if not member:
        raise HTTPException(status_code=404, detail=err("Family member not found.", "NOT_FOUND"))

    await family_service.delete_family_member(member, db)
    return ok(message="Family member removed.")


@router.post("/invite", status_code=status.HTTP_201_CREATED, summary="Send a family invite")
async def send_invite(
    data: FamilyInviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Send an invite link to a family member via email or SMS.

    The invite contains a unique token that the family member uses to join
    the platform and link their account to the inviter's family tree.
    """
    member = await family_service.get_family_member(data.family_member_id, current_user.id, db)
    if not member:
        raise HTTPException(status_code=404, detail=err("Family member not found.", "NOT_FOUND"))

    if not data.invitee_email and not data.invitee_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err("Provide either invitee_email or invitee_phone.", "MISSING_CONTACT"),
        )

    invite = await family_service.create_invite(
        inviter_id=current_user.id,
        family_member=member,
        invitee_email=data.invitee_email,
        invitee_phone=data.invitee_phone,
        db=db,
        redis=redis,
    )

    # Send invite email if email provided
    if data.invitee_email:
        invite_link = f"{settings.INVITE_BASE_URL}/{invite.token}"
        await send_invite_email(
            to_email=data.invitee_email,
            inviter_name=current_user.full_name,
            relationship=member.relationship,
            invite_link=invite_link,
        )

    return ok(
        data=FamilyInviteOut.model_validate(invite).model_dump(),
        message="Invite sent successfully.",
    )


@router.get("/tree", summary="Get the full family tree")
async def get_family_tree(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the full family tree structure with health conditions per node.

    Used by the Family Health page to render the generational SVG map.
    """
    tree = await family_service.get_family_tree(
        user_id=current_user.id,
        user_name=current_user.full_name,
        db=db,
    )
    return ok(data=tree.model_dump(), message="Family tree retrieved.")


@router.get("/shared-risks", summary="Get hereditary disease patterns")
async def get_shared_risks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Detect and return hereditary disease patterns across the user's family.

    Diseases appearing in 2+ family members are flagged as hereditary patterns.
    """
    patterns = await family_service.detect_hereditary_patterns(current_user.id, db)
    return ok(
        data=HereditaryPatternsOut(
            patterns=patterns,
            user_id=current_user.id,
            total_patterns=len(patterns),
        ).model_dump(),
        message=f"{len(patterns)} hereditary pattern(s) detected.",
    )
