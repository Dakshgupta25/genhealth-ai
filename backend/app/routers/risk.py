"""
Risk Analysis router.

Endpoints:
  GET  /profile              - User's full risk profile
  GET  /predictions          - List all active risk predictions
  POST /generate             - Trigger risk model re-run
  GET  /predictions/:disease - Single disease risk detail
  GET  /family-risk          - Family-level hereditary risk map
  GET  /watchlist            - Top flagged future risks
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.risk_prediction import RiskPrediction
from app.models.user import User
from app.schemas.common import ok, err
from app.schemas.risk import (
    FamilyRiskMapOut,
    FamilyRiskNode,
    RiskGenerateIn,
    RiskPredictionOut,
    RiskProfileOut,
    WatchlistItem,
    WatchlistOut,
)
from app.services.insight_service import compute_health_score
from app.services.family_service import get_family_tree

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/predictions", summary="List all active risk predictions")
async def list_predictions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all active disease risk predictions for the authenticated user."""
    result = await db.execute(
        select(RiskPrediction).where(
            and_(RiskPrediction.user_id == current_user.id, RiskPrediction.is_active == True)
        )
    )
    predictions = result.scalars().all()
    return ok(
        data=[RiskPredictionOut.model_validate(p).model_dump() for p in predictions],
        message=f"{len(predictions)} active prediction(s).",
    )


@router.get("/profile", summary="Get full risk profile")
async def get_risk_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the user's full risk profile: all active predictions + health score.

    Predictions are sorted by probability descending.
    """
    result = await db.execute(
        select(RiskPrediction).where(
            and_(RiskPrediction.user_id == current_user.id, RiskPrediction.is_active == True)
        )
    )
    predictions = list(result.scalars().all())
    predictions.sort(key=lambda p: p.probability, reverse=True)

    health_score = await compute_health_score(current_user.id, db)

    high = sum(1 for p in predictions if p.risk_level == "high")
    moderate = sum(1 for p in predictions if p.risk_level == "moderate")
    low = sum(1 for p in predictions if p.risk_level == "low")

    overall = "high" if high > 0 else "moderate" if moderate > 0 else "low"
    last_updated = max((p.generated_at for p in predictions), default=None)

    profile = RiskProfileOut(
        user_id=current_user.id,
        overall_risk_level=overall,
        health_score=health_score,
        predictions=[RiskPredictionOut.model_validate(p) for p in predictions],
        total_predictions=len(predictions),
        high_risk_count=high,
        moderate_risk_count=moderate,
        low_risk_count=low,
        last_updated=last_updated,
    )
    return ok(data=profile.model_dump(), message="Risk profile retrieved.")


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED, summary="Trigger risk model re-run")
async def generate_risk(
    body: RiskGenerateIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dispatch a Celery task to re-run the risk prediction model.

    Specify a disease_name to refresh a single prediction, or leave it
    empty to regenerate the full risk profile.
    """
    try:
        from app.celery_app import celery_app
        task = celery_app.send_task(
            "app.tasks.risk_tasks.compute_user_risk",
            args=[str(current_user.id), body.disease_name],
            kwargs={"force": body.force},
            queue="risk",
        )
        return ok(
            data={"task_id": task.id, "state": "PENDING"},
            message="Risk generation queued. Check back in a few moments.",
        )
    except Exception as exc:
        logger.exception("Failed to dispatch risk task: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=err("Risk service is temporarily unavailable.", "SERVICE_UNAVAILABLE"),
        )


@router.get("/predictions/{disease_name}", summary="Get single disease risk detail")
async def get_disease_risk(
    disease_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the detailed risk prediction for a specific disease."""
    result = await db.execute(
        select(RiskPrediction).where(
            and_(
                RiskPrediction.user_id == current_user.id,
                RiskPrediction.is_active == True,
                RiskPrediction.disease_name.ilike(f"%{disease_name}%"),
            )
        )
    )
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(
            status_code=404,
            detail=err(f"No active prediction found for '{disease_name}'.", "NOT_FOUND"),
        )
    return ok(
        data=RiskPredictionOut.model_validate(prediction).model_dump(),
        message="Prediction retrieved.",
    )


@router.get("/family-risk", summary="Get family-level hereditary risk map")
async def get_family_risk(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return a risk map overlaying each family member's conditions onto the tree.

    Used by the Doctor Portal's Generational Insight panel.
    """
    tree = await get_family_tree(current_user.id, current_user.full_name, db)
    result = await db.execute(
        select(RiskPrediction).where(
            and_(RiskPrediction.user_id == current_user.id, RiskPrediction.is_active == True)
        )
    )
    user_predictions = list(result.scalars().all())

    hereditary_diseases = list({
        condition
        for node in tree.members
        for condition in node.conditions
    })

    family_nodes = [
        FamilyRiskNode(
            family_member_id=node.id,
            name=node.name,
            relationship=node.relationship,
            generation=node.generation,
            conditions=node.conditions,
        )
        for node in tree.members
    ]

    risk_map = FamilyRiskMapOut(
        user_id=current_user.id,
        family_nodes=family_nodes,
        hereditary_diseases=hereditary_diseases,
        user_predictions=[RiskPredictionOut.model_validate(p) for p in user_predictions],
    )
    return ok(data=risk_map.model_dump(), message="Family risk map retrieved.")


@router.get("/watchlist", summary="Get top-flagged disease watchlist")
async def get_watchlist(
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the top N highest-risk conditions the user should watch.

    Includes the family members that contributed to each risk and a
    recommended action for each item.
    """
    result = await db.execute(
        select(RiskPrediction).where(
            and_(RiskPrediction.user_id == current_user.id, RiskPrediction.is_active == True)
        )
        .order_by(RiskPrediction.probability.desc())
        .limit(limit)
    )
    predictions = result.scalars().all()

    items = []
    for pred in predictions:
        family_sources = [
            f["factor"] for f in (pred.contributing_factors or []) if f.get("source") == "family"
        ]
        # Determine a recommended action based on risk level
        if pred.risk_level == "high":
            action = "Schedule an immediate consultation with a specialist."
        elif pred.risk_level == "moderate":
            action = "Request an annual screening test and monitor regularly."
        else:
            action = "Maintain healthy lifestyle habits and monitor annually."

        items.append(
            WatchlistItem(
                disease_name=pred.disease_name,
                icd10_code=pred.icd10_code,
                probability=pred.probability,
                probability_pct=pred.probability_pct,
                risk_level=pred.risk_level,
                reason=f"Based on your risk profile and family history.",
                family_members_affected=family_sources[:3],
                recommended_action=action,
            )
        )

    return ok(
        data=WatchlistOut(user_id=current_user.id, items=items, total=len(items)).model_dump(),
        message=f"Top {len(items)} watchlist item(s).",
    )
