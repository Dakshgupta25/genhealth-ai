"""
Users router.

Endpoints:
  GET  /users/me         - Alias (profile via auth router)
  GET  /users/:id        - Get user by ID (admin only)
  GET  /users            - List users (admin only, paginated)
  DELETE /users/:id      - Delete user account (admin or self)
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_role
from app.models.user import User
from app.schemas.common import ok, err, PaginationMeta
from app.schemas.user import UserOut

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", summary="List all users (admin only)")
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Return a paginated list of all registered users.

    Restricted to admin role only.
    """
    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar_one()

    offset = (page - 1) * per_page
    result = await db.execute(select(User).offset(offset).limit(per_page))
    users = result.scalars().all()

    total_pages = (total + per_page - 1) // per_page
    meta = PaginationMeta(
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )

    return {
        "success": True,
        "data": [UserOut.model_validate(u).model_dump() for u in users],
        "meta": meta.model_dump(),
        "message": f"{total} users found.",
    }


@router.get("/{user_id}", summary="Get user by ID")
async def get_user(
    user_id: UUID,
    current_user: User = Depends(require_role(["admin", "doctor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch a user by their UUID.

    Accessible by admins and doctors (doctors see patient data they have access to).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=err("User not found.", "USER_NOT_FOUND"))
    return ok(data=UserOut.model_validate(user).model_dump(), message="User retrieved.")


@router.delete("/{user_id}", summary="Delete a user account")
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a user account.

    Users can delete their own account. Admins can delete any account.
    """
    # Allow self-deletion or admin deletion
    if str(current_user.id) != str(user_id) and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err("You can only delete your own account.", "FORBIDDEN"),
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=err("User not found.", "USER_NOT_FOUND"))

    # 1. Delete associated files from S3/MinIO
    try:
        from app.models.health_record import HealthRecord
        from app.services.record_service import _get_s3_client
        # Fetch keys of all records
        records_res = await db.execute(select(HealthRecord.source_file_key).where(HealthRecord.owner_id == user_id))
        s3_keys = [k for k in records_res.scalars().all() if k]
        if s3_keys:
            s3 = _get_s3_client()
            for key in s3_keys:
                try:
                    s3.delete_object(Bucket=settings.AWS_BUCKET_NAME, Key=key)
                    logger.info("Deleted S3 object: %s during user %s deletion", key, user_id)
                except Exception as s3_exc:
                    logger.warning("Failed to delete S3 object %s during user deletion: %s", key, s3_exc)
    except Exception as exc:
        logger.exception("Failed to delete S3 objects during user deletion: %s", exc)

    # 2. Delete MongoDB collections
    try:
        from app.database import get_mongo_db
        mongo_db = get_mongo_db()
        # Delete user risk profiles
        await mongo_db["risk_profiles"].delete_many({"user_id": str(user_id)})
        # Delete user OCR results
        await mongo_db["ocr_results"].delete_many({"owner_id": str(user_id)})
        logger.info("Deleted MongoDB records for user %s during deletion", user_id)
    except Exception as exc:
        logger.exception("Failed to delete MongoDB data for user %s: %s", user_id, exc)

    await db.delete(user)
    logger.info("User %s deleted by %s.", user_id, current_user.id)
    return ok(message="Account deleted successfully.")
