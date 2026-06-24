"""
Authentication service.

Handles all auth business logic:
  - Password hashing and verification (bcrypt)
  - JWT access + refresh token creation/validation
  - Refresh token storage in Redis
  - Email OTP generation/verification
  - Password reset token management
"""

import logging
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import redis.asyncio as aioredis
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.schemas.user import UserCreate, TokenOut

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Password hashing ─────────────────────────────────────────────────────────
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of the given plain-text password."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT ──────────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(tz=timezone.utc)


def create_access_token(user_id: str, role: str) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        user_id: User's UUID as a string.
        role:    User's role ('patient', 'doctor', 'admin').

    Returns:
        Signed JWT string with 'sub', 'role', 'type', 'iat', 'exp' claims.
    """
    expire = _utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": _utcnow(),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """
    Create a long-lived JWT refresh token.

    Refresh tokens have a 'type': 'refresh' claim so they cannot be used
    as access tokens. A hash of this token is stored in Redis.
    """
    expire = _utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": secrets.token_hex(16),   # Unique token ID for revocation
        "iat": _utcnow(),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Raises:
        JWTError: If the token is invalid, expired, or malformed.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ─── Refresh token Redis storage ──────────────────────────────────────────────

_REFRESH_KEY_PREFIX = "refresh:"


async def store_refresh_token(
    user_id: str, token: str, redis: aioredis.Redis
) -> None:
    """
    Store a refresh token hash in Redis with TTL.

    We store only the last issued refresh token per user. Issuing a new
    refresh token implicitly invalidates the previous one.
    """
    key = f"{_REFRESH_KEY_PREFIX}{user_id}"
    expire_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    # Store a hash (not the full token) to mitigate Redis data exposure
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    await redis.set(key, token_hash, ex=expire_seconds)
    logger.debug("Refresh token stored for user %s (expires in %ds).", user_id, expire_seconds)


async def validate_refresh_token(
    user_id: str, token: str, redis: aioredis.Redis
) -> bool:
    """
    Verify that a refresh token matches the stored hash in Redis.

    Returns False if the token is not found (expired or revoked).
    """
    import hashlib
    key = f"{_REFRESH_KEY_PREFIX}{user_id}"
    stored_hash = await redis.get(key)
    if not stored_hash:
        return False
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return secrets.compare_digest(stored_hash, token_hash)


async def revoke_refresh_token(user_id: str, redis: aioredis.Redis) -> None:
    """Remove a user's refresh token from Redis (effectively logging them out)."""
    key = f"{_REFRESH_KEY_PREFIX}{user_id}"
    await redis.delete(key)
    logger.debug("Refresh token revoked for user %s.", user_id)


# ─── OTP ──────────────────────────────────────────────────────────────────────

_OTP_KEY_PREFIX = "otp:"


def _generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP of the given length."""
    return "".join(random.choices(string.digits, k=length))


async def create_and_store_otp(email: str, redis: aioredis.Redis) -> str:
    """
    Generate a 6-digit OTP, store it in Redis, and return it.

    The OTP expires after OTP_EXPIRE_MINUTES. A new call replaces the
    previous OTP for that email.
    """
    otp = _generate_otp()
    key = f"{_OTP_KEY_PREFIX}{email.lower()}"
    expire_seconds = settings.OTP_EXPIRE_MINUTES * 60
    await redis.set(key, otp, ex=expire_seconds)
    logger.debug("OTP created for email %s (expires in %ds).", email, expire_seconds)
    return otp


async def verify_otp(email: str, otp: str, redis: aioredis.Redis) -> bool:
    """
    Verify an OTP for a given email and delete it on success (one-time use).

    Returns True if the OTP matches, False otherwise.
    """
    key = f"{_OTP_KEY_PREFIX}{email.lower()}"
    stored_otp = await redis.get(key)
    if not stored_otp:
        return False
    if secrets.compare_digest(stored_otp, otp):
        await redis.delete(key)   # One-time use
        return True
    return False


# ─── Password reset ───────────────────────────────────────────────────────────

_RESET_KEY_PREFIX = "pwd_reset:"
_RESET_TOKEN_EXPIRE_MINUTES = 30


async def create_password_reset_token(
    user_id: str, redis: aioredis.Redis
) -> str:
    """
    Generate a secure URL-safe reset token and store the user_id mapping in Redis.

    Returns the token (to be embedded in the reset link).
    """
    token = secrets.token_urlsafe(32)
    key = f"{_RESET_KEY_PREFIX}{token}"
    await redis.set(key, str(user_id), ex=_RESET_TOKEN_EXPIRE_MINUTES * 60)
    return token


async def validate_password_reset_token(
    token: str, redis: aioredis.Redis
) -> Optional[str]:
    """
    Validate a password reset token and return the associated user_id.

    Deletes the token on success (single use).
    Returns None if the token is invalid or expired.
    """
    key = f"{_RESET_KEY_PREFIX}{token}"
    user_id = await redis.get(key)
    if user_id:
        await redis.delete(key)
    return user_id


# ─── User queries ─────────────────────────────────────────────────────────────

async def get_user_by_email(email: str, db: AsyncSession) -> Optional[User]:
    """Fetch a user by email address (case-insensitive)."""
    result = await db.execute(
        select(User).where(User.email == email.lower().strip())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(user_id: UUID, db: AsyncSession) -> Optional[User]:
    """Fetch a user by UUID primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(user_in: UserCreate, db: AsyncSession) -> User:
    """
    Create a new user account.

    Hashes the password, normalizes the email, and persists the user.
    The user is returned as an ORM object (not yet committed — the caller
    controls the transaction via the session dependency).
    """
    user = User(
        email=user_in.email.lower().strip(),
        password_hash=hash_password(user_in.password),
        full_name=user_in.full_name.strip(),
        date_of_birth=user_in.date_of_birth,
        gender=user_in.gender,
        blood_group=user_in.blood_group,
        phone=user_in.phone,
        role=user_in.role,
        is_verified=False,
    )
    db.add(user)
    await db.flush()   # Get the UUID without committing
    logger.info("Created new user: %s (role=%s).", user.email, user.role)
    return user


def build_token_response(user: User, access_token: str, refresh_token: str) -> TokenOut:
    """Assemble a TokenOut schema from a user and its new tokens."""
    return TokenOut(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
