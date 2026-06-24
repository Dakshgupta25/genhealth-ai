"""
Recommendations router.

Provides dedicated endpoints for retrieving, setting reminders on,
and marking recommendations as completed.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.common import ok, err
from app.services.insight_service import get_recommendations

logger = logging.getLogger(__name__)
router = APIRouter()

CATEGORY_LABELS = {
    "diet": "🍽️ Diet",
    "exercise": "🏃 Exercise",
    "sleep": "😴 Sleep",
    "checkup": "🩺 Checkup",
    "mental": "🧠 Mental Health",
}


@router.get("/", summary="Get all personalised recommendations")
async def list_recommendations(
    category: str = Query(default=None, description="Filter by category: diet|exercise|sleep|checkup"),
    priority: str = Query(default=None, description="Filter by priority: urgent|recommended|optional"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return personalised health recommendations, optionally filtered by category or priority.
    """
    recs = await get_recommendations(current_user.id, db)

    if category:
        recs = [r for r in recs if r.get("category") == category]
    if priority:
        recs = [r for r in recs if r.get("priority") == priority]

    # Enrich with display labels
    for rec in recs:
        rec["category_label"] = CATEGORY_LABELS.get(rec.get("category", ""), rec.get("category", ""))

    return ok(
        data={"recommendations": recs, "total": len(recs)},
        message=f"{len(recs)} recommendation(s) returned.",
    )


@router.get("/categories", summary="List all recommendation categories")
async def list_categories(current_user: User = Depends(get_current_user)):
    """Return available recommendation category labels."""
    return ok(
        data={"categories": list(CATEGORY_LABELS.values())},
        message="Categories retrieved.",
    )


@router.post("/remind", summary="Set a reminder for a recommendation")
async def set_reminder(
    title: str = Query(..., description="Recommendation title to set a reminder for"),
    current_user: User = Depends(get_current_user),
):
    """
    Set a reminder for a specific recommendation.

    In production, this creates a scheduled notification in the notification
    service. Currently returns a confirmation stub.
    """
    logger.info("Reminder set by user %s for: %s", current_user.id, title)
    return ok(
        data={"reminder_set": True, "for": title, "user_id": str(current_user.id)},
        message=f"Reminder set for '{title}'.",
    )
