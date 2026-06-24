"""
Authentication router.

Endpoints:
  POST /signup              - Register a new user
  POST /login               - Login with email + password
  POST /refresh             - Refresh access token
  POST /logout              - Revoke refresh token
  POST /verify-email        - Verify email via OTP
  POST /forgot-password     - Request password reset link
  POST /reset-password      - Apply password reset
  GET  /me                  - Get current user profile
  PATCH /me                 - Update profile
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.database import get_db, get_redis
from app.middleware.auth_middleware import get_current_user
from app.middleware.rate_limiter import rate_limit
from app.models.user import User
from app.schemas.common import ok, err
from app.schemas.user import (
    OTPVerify,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenIn,
    TokenOut,
    UserCreate,
    UserLogin,
    UserOut,
    UserUpdate,
)
from app.services import auth_service
from app.services.notification_service import (
    send_otp_email,
    send_password_reset_email,
    send_welcome_email,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    dependencies=[Depends(rate_limit(limit=5, window=60))],
)
async def signup(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Register a new patient or doctor account.

    - Validates email uniqueness
    - Hashes password with bcrypt (rounds=12)
    - Sends OTP verification email
    - Returns JWT token pair for immediate use (account is usable before verification)
    """
    # Check email uniqueness
    existing = await auth_service.get_user_by_email(user_in.email, db)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=err("Email address is already registered.", "EMAIL_EXISTS"),
        )

    user = await auth_service.create_user(user_in, db)

    # Issue tokens immediately so the user can start using the app
    access_token = auth_service.create_access_token(str(user.id), user.role)
    refresh_token = auth_service.create_refresh_token(str(user.id))
    await auth_service.store_refresh_token(str(user.id), refresh_token, redis)

    # Send verification OTP
    otp = await auth_service.create_and_store_otp(user.email, redis)
    await send_otp_email(user.email, otp, user.full_name)
    await send_welcome_email(user.email, user.full_name)

    token_data = auth_service.build_token_response(user, access_token, refresh_token)

    return ok(
        data={"user": UserOut.model_validate(user).model_dump(), "tokens": token_data.model_dump()},
        message="Account created. Please verify your email.",
    )


@router.post(
    "/login",
    summary="Authenticate and get JWT tokens",
    dependencies=[Depends(rate_limit(limit=10, window=60))],
)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Authenticate with email and password.

    Returns a short-lived access token (15 min) and a long-lived
    refresh token (7 days). Store the refresh token securely.
    """
    user = await auth_service.get_user_by_email(credentials.email, db)
    if not user or not auth_service.verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err("Invalid email or password.", "INVALID_CREDENTIALS"),
        )

    access_token = auth_service.create_access_token(str(user.id), user.role)
    refresh_token = auth_service.create_refresh_token(str(user.id))
    await auth_service.store_refresh_token(str(user.id), refresh_token, redis)

    token_data = auth_service.build_token_response(user, access_token, refresh_token)

    return ok(
        data={"user": UserOut.model_validate(user).model_dump(), "tokens": token_data.model_dump()},
        message="Login successful.",
    )


@router.post("/refresh", summary="Refresh the access token")
async def refresh_token(
    body: RefreshTokenIn,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Exchange a valid refresh token for a new access token.

    The old refresh token is replaced with a new one (token rotation).
    """
    from jose import JWTError
    try:
        payload = auth_service.decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err("Invalid or expired refresh token.", "INVALID_REFRESH_TOKEN"),
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err("Token type mismatch.", "INVALID_TOKEN_TYPE"),
        )

    user_id = payload.get("sub")
    is_valid = await auth_service.validate_refresh_token(user_id, body.refresh_token, redis)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err("Refresh token has been revoked or expired.", "TOKEN_REVOKED"),
        )

    user = await auth_service.get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=404, detail=err("User not found.", "USER_NOT_FOUND"))

    # Rotate tokens
    new_access = auth_service.create_access_token(str(user.id), user.role)
    new_refresh = auth_service.create_refresh_token(str(user.id))
    await auth_service.store_refresh_token(str(user.id), new_refresh, redis)

    return ok(
        data=auth_service.build_token_response(user, new_access, new_refresh).model_dump(),
        message="Token refreshed.",
    )


@router.post("/logout", summary="Invalidate refresh token (logout)")
async def logout(
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Revoke the user's refresh token, effectively logging them out."""
    await auth_service.revoke_refresh_token(str(current_user.id), redis)
    return ok(message="Logged out successfully.")


@router.post("/verify-email", summary="Verify email address via OTP")
async def verify_email(
    body: OTPVerify,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Verify a user's email address using the 6-digit OTP sent on signup.
    """
    user = await auth_service.get_user_by_email(body.email, db)
    if not user:
        raise HTTPException(status_code=404, detail=err("User not found.", "USER_NOT_FOUND"))

    is_valid = await auth_service.verify_otp(body.email, body.otp, redis)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err("Invalid or expired OTP.", "INVALID_OTP"),
        )

    user.is_verified = True
    user.email_verified_at = datetime.now(tz=timezone.utc)
    db.add(user)
    return ok(message="Email verified successfully.")


@router.post("/forgot-password", summary="Request a password reset link")
async def forgot_password(
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Send a password reset link to the given email if it exists.

    Always returns 200 to prevent email enumeration.
    """
    user = await auth_service.get_user_by_email(body.email, db)
    if user:
        token = await auth_service.create_password_reset_token(str(user.id), redis)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        await send_password_reset_email(body.email, reset_link, user.full_name)

    return ok(message="If that email exists, a reset link has been sent.")


@router.post("/reset-password", summary="Reset password with a valid token")
async def reset_password(
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Apply a new password using a valid reset token."""
    from app.config import get_settings as _gs
    user_id = await auth_service.validate_password_reset_token(body.token, redis)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err("Reset token is invalid or has expired.", "INVALID_RESET_TOKEN"),
        )

    from uuid import UUID
    user = await auth_service.get_user_by_id(UUID(user_id), db)
    if not user:
        raise HTTPException(status_code=404, detail=err("User not found.", "USER_NOT_FOUND"))

    user.password_hash = auth_service.hash_password(body.new_password)
    db.add(user)
    # Revoke all refresh tokens on password change
    await auth_service.revoke_refresh_token(str(user.id), redis)
    return ok(message="Password reset successfully. Please log in again.")


@router.get("/me", summary="Get current user profile")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile data."""
    return ok(data=UserOut.model_validate(current_user).model_dump(), message="Profile retrieved.")


@router.patch("/me", summary="Update current user profile")
async def update_me(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Partially update the authenticated user's profile."""
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.add(current_user)
    return ok(data=UserOut.model_validate(current_user).model_dump(), message="Profile updated.")


# Import settings at module level (used in forgot_password)
from app.config import get_settings as _get_settings_local
settings = _get_settings_local()
