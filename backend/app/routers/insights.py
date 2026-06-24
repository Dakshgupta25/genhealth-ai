"""
Insights router.

Endpoints:
  GET /health-score        - Computed health score (0–100)
  GET /trends              - Disease frequency over time
  GET /summary             - AI-generated health summary
  GET /recommendations     - Personalized recommendations list
  GET /heatmap             - Recurrence heatmap data
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.common import ok
from app.services.insight_service import (
    compute_health_score,
    generate_health_summary,
    get_disease_trends,
    get_recommendations,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health-score", summary="Get computed health score")
async def get_health_score(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute and return the user's current health score (0–100).

    The score is derived from active risk predictions and engagement metrics.
    Higher scores = better health standing.
    """
    score = await compute_health_score(current_user.id, db)
    level = "good" if score >= 80 else "moderate" if score >= 60 else "needs_attention"
    return ok(
        data={"score": score, "level": level, "user_id": str(current_user.id)},
        message=f"Health score: {score}/100.",
    )


@router.get("/trends", summary="Get disease frequency trends")
async def get_trends(
    months: int = Query(default=12, ge=1, le=60, description="Lookback period in months"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return disease mention frequency over the past N months.

    Useful for identifying recurring conditions over time.
    """
    trends = await get_disease_trends(current_user.id, db, months=months)
    return ok(
        data={"trends": trends, "months": months},
        message=f"{len(trends)} trend(s) over the past {months} months.",
    )


@router.get("/summary", summary="Get AI-generated health summary")
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a personalised health summary using risk and record data.

    In production, this integrates with an LLM for natural language generation.
    Currently uses a template-based approach with real database data.
    """
    summary = await generate_health_summary(current_user.id, current_user.full_name, db)
    return ok(data=summary, message="Health summary generated.")


@router.get("/recommendations", summary="Get personalised recommendations")
async def get_recommendations_list(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return a list of personalised health recommendations.

    Recommendations are ranked by priority (urgent → recommended → optional)
    and matched to the user's active risk conditions.
    """
    recs = await get_recommendations(current_user.id, db)
    return ok(
        data={"recommendations": recs, "total": len(recs)},
        message=f"{len(recs)} recommendation(s) generated.",
    )


@router.get("/heatmap", summary="Get disease recurrence heatmap data")
async def get_heatmap(
    months: int = Query(default=12, ge=1, le=60),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return heatmap-ready data showing record activity per month.

    Returns month labels and counts for visualising health engagement.
    """
    from sqlalchemy import select, func, extract
    from app.models.health_record import HealthRecord
    from datetime import datetime, timedelta

    since = datetime.utcnow() - timedelta(days=months * 30)
    result = await db.execute(
        select(
            func.to_char(HealthRecord.created_at, "YYYY-MM").label("month"),
            func.count(HealthRecord.id).label("count"),
        )
        .where(HealthRecord.owner_id == current_user.id)
        .where(HealthRecord.created_at >= since)
        .group_by("month")
        .order_by("month")
    )
    rows = result.all()
    heatmap = [{"month": row[0], "count": row[1]} for row in rows]

    return ok(
        data={"heatmap": heatmap, "months": months},
        message=f"Heatmap data for {months} months.",
    )
