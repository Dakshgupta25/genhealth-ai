"""
Invite router (public-facing).

Endpoints:
  GET  /invite/:token         - Validate invite token (public, no auth required)
  POST /invite/:token/accept  - Accept invite, create account, link family tree
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db, get_redis
from app.schemas.common import ok, err
from app.schemas.family import InviteAcceptIn, FamilyInviteOut
from app.schemas.user import UserCreate, UserOut, TokenOut
from app.services.family_service import validate_invite_token, accept_invite
from app.services import auth_service
from app.services.notification_service import send_welcome_email

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{token}", summary="Validate an invite token (public)")
async def validate_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate a family invite token and return invite details.

    This endpoint is public (no auth required) so the invitee can see
    who invited them before creating an account.

    Returns invite metadata if valid; 404 if not found or expired.
    """
    invite = await validate_invite_token(token, db)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err("Invite link is invalid, expired, or already used.", "INVALID_INVITE"),
        )

    return ok(
        data={
            "valid": True,
            "inviter_name": invite.inviter.full_name if invite.inviter else "Someone",
            "relationship": invite.relationship,
            "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
            "family_member_id": str(invite.family_member_id) if invite.family_member_id else None,
        },
        message="Invite is valid.",
    )


@router.post("/{token}/accept", status_code=status.HTTP_201_CREATED, summary="Accept an invite")
async def accept_invite_endpoint(
    token: str,
    body: InviteAcceptIn,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Accept a family invite by creating a new account.

    **Flow:**
    1. Validate the invite token.
    2. Check that the email is not already registered.
    3. Create a new user account using the provided details.
    4. Link the new user to the inviter's family tree.
    5. Return JWT tokens for immediate login.

    If the invitee already has an account, they should log in normally
    and link their account from the Family Health page.
    """
    # Validate token
    invite = await validate_invite_token(token, db)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err("Invite link is invalid, expired, or already used.", "INVALID_INVITE"),
        )

    # Check email uniqueness
    existing = await auth_service.get_user_by_email(body.email, db)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=err(
                "An account with this email already exists. "
                "Please log in and link your account instead.",
                "EMAIL_EXISTS",
            ),
        )

    # Create the new user account
    user_create = UserCreate(
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        date_of_birth=body.date_of_birth,
        gender=body.gender,
        role="patient",
    )
    new_user = await auth_service.create_user(user_create, db)

    # Auto-verify since they arrived via invite link (email already trusted)
    new_user.is_verified = True
    new_user.email_verified_at = datetime.now(tz=timezone.utc)
    db.add(new_user)

    # Link the new user to the inviter's family tree
    await accept_invite(invite, new_user, db, redis)

    # Issue JWT tokens
    access_token = auth_service.create_access_token(str(new_user.id), new_user.role)
    refresh_token = auth_service.create_refresh_token(str(new_user.id))
    await auth_service.store_refresh_token(str(new_user.id), refresh_token, redis)

    token_data = auth_service.build_token_response(new_user, access_token, refresh_token)

    # Welcome email
    await send_welcome_email(new_user.email, new_user.full_name)

    logger.info(
        "Invite accepted: new user %s linked to family tree of inviter %s.",
        new_user.id,
        invite.inviter_id,
    )

    return ok(
        data={
            "user": UserOut.model_validate(new_user).model_dump(),
            "tokens": token_data.model_dump(),
            "linked_to": str(invite.inviter_id),
        },
        message="Account created and family tree linked successfully.",
    )
