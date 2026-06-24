"""
Authentication middleware and dependency helpers.

Provides:
  - `get_current_user`: FastAPI dependency that validates JWT and returns the User
  - `require_role`: Factory that produces role-checked dependencies
  - `get_optional_user`: Non-raising version for public endpoints
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import decode_token, get_user_by_id

logger = logging.getLogger(__name__)

# Extracts Bearer token from the Authorization header
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: validate the JWT and return the authenticated User.

    Raises:
        HTTP 401 if the token is missing, invalid, expired, or the user
        no longer exists in the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "success": False,
            "error": "Authentication required. Please provide a valid access token.",
            "code": "UNAUTHORIZED",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        raise credentials_exception

    # Validate token type (must be 'access', not 'refresh')
    if payload.get("type") != "access":
        raise credentials_exception

    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = await get_user_by_id(user_id, db)
    if user is None:
        logger.warning("JWT references non-existent user_id=%s.", user_id)
        raise credentials_exception

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    FastAPI dependency: return the authenticated User or None (no exception).

    Use on public endpoints that behave differently for authenticated users.
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_role(roles: List[str]):
    """
    Dependency factory that enforces role-based access control.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            current_user: User = Depends(require_role(["admin"]))
        ):
            ...

    Args:
        roles: List of allowed role strings (e.g., ['doctor', 'admin']).

    Returns:
        A FastAPI dependency function that raises HTTP 403 if the user's
        role is not in the allowed list.
    """
    async def _check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error": (
                        f"This endpoint requires one of the following roles: "
                        f"{', '.join(roles)}. Your role is '{current_user.role}'."
                    ),
                    "code": "FORBIDDEN",
                },
            )
        return current_user

    return _check_role


def require_verified(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency: enforce that the user has verified their email.

    Use on sensitive endpoints that should only be accessible to verified accounts.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": "Email verification required. Please verify your email address.",
                "code": "EMAIL_NOT_VERIFIED",
            },
        )
    return current_user
