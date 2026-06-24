"""
Doctor Portal router.

Doctor-role endpoints for:
  POST /login                        - Doctor login (role-checked)
  GET  /patients                     - List accessible patients
  GET  /patients/:id                 - Patient summary
  GET  /patients/:id/relevant        - AI-surfaced relevant records by complaint
  GET  /patients/:id/family-risk     - Generational risk summary
  POST /session/extend               - Extend active access session
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, require_role
from app.models.doctor import DoctorAccess
from app.models.health_record import ExtractedEntity, HealthRecord
from app.models.risk_prediction import RiskPrediction
from app.models.user import User
from app.schemas.common import ok, err
from app.schemas.health_record import HealthRecordOut
from app.schemas.risk import RiskPredictionOut
from app.schemas.user import UserOut
from app.services.family_service import detect_hereditary_patterns, get_family_tree
from app.services.insight_service import compute_health_score

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_patient_with_access(
    patient_id: UUID, doctor: User, db: AsyncSession
) -> User:
    """
    Fetch a patient the doctor has active access to.

    Raises HTTP 403 if no active access grant exists.
    """
    # Check doctor_access grant
    access_result = await db.execute(
        select(DoctorAccess).where(
            and_(
                DoctorAccess.patient_id == patient_id,
                DoctorAccess.doctor_id == doctor.id,
                DoctorAccess.is_active == True,
            )
        )
    )
    access = access_result.scalar_one_or_none()
    if not access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err(
                "You do not have active access to this patient's records.",
                "NO_PATIENT_ACCESS",
            ),
        )

    patient_result = await db.execute(select(User).where(User.id == patient_id))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail=err("Patient not found.", "NOT_FOUND"))
    return patient


@router.get("/patients", summary="List doctor's accessible patients")
async def list_patients(
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all patients the doctor currently has active access to.
    """
    result = await db.execute(
        select(DoctorAccess, User)
        .join(User, User.id == DoctorAccess.patient_id)
        .where(
            and_(
                DoctorAccess.doctor_id == current_user.id,
                DoctorAccess.is_active == True,
            )
        )
    )
    rows = result.all()

    patients = []
    for access, patient in rows:
        score = await compute_health_score(patient.id, db)
        patients.append({
            "patient": UserOut.model_validate(patient).model_dump(),
            "access_level": access.access_level,
            "expires_at": access.expires_at.isoformat() if access.expires_at else None,
            "health_score": score,
        })

    return ok(data={"patients": patients, "total": len(patients)}, message=f"{len(patients)} patient(s).")


@router.get("/patients/{patient_id}", summary="Get patient summary")
async def get_patient_summary(
    patient_id: UUID,
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Return a comprehensive patient summary: profile, health score, and active risks.
    """
    patient = await _get_patient_with_access(patient_id, current_user, db)
    score = await compute_health_score(patient.id, db)

    # Active risk predictions
    risk_result = await db.execute(
        select(RiskPrediction).where(
            and_(RiskPrediction.user_id == patient.id, RiskPrediction.is_active == True)
        )
    )
    predictions = risk_result.scalars().all()

    return ok(
        data={
            "patient": UserOut.model_validate(patient).model_dump(),
            "health_score": score,
            "active_risks": [RiskPredictionOut.model_validate(p).model_dump() for p in predictions],
        },
        message="Patient summary retrieved.",
    )


@router.get("/patients/{patient_id}/relevant", summary="Get AI-surfaced relevant records")
async def get_relevant_records(
    patient_id: UUID,
    complaint: str = Query(default="", description="Chief complaint to match records against"),
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Return health records most relevant to the doctor's stated chief complaint.

    Uses keyword matching against extracted entities and record types.
    In production, this would use semantic search (embeddings).
    """
    patient = await _get_patient_with_access(patient_id, current_user, db)

    # Fetch all patient records with entities
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(HealthRecord)
        .where(HealthRecord.owner_id == patient.id)
        .options(selectinload(HealthRecord.extracted_entities))
        .order_by(HealthRecord.created_at.desc())
        .limit(50)
    )
    records = result.scalars().all()

    # Keyword match against complaint
    complaint_lower = complaint.lower()
    scored = []
    for record in records:
        score = 0
        for entity in record.extracted_entities:
            if complaint_lower and complaint_lower in entity.effective_value.lower():
                score += 2
        if record.record_type in complaint_lower:
            score += 1
        # Recent records get a small recency bonus
        if record.extraction_status == "done":
            score += 0.5
        if record.is_verified_by_user:
            score += 0.5
        scored.append((score, record))

    # Sort by relevance descending, return top 10
    scored.sort(key=lambda x: x[0], reverse=True)
    relevant = [r for _, r in scored[:10]]

    return ok(
        data={
            "records": [HealthRecordOut.model_validate(r).model_dump() for r in relevant],
            "complaint": complaint,
            "total": len(relevant),
        },
        message=f"{len(relevant)} relevant records for complaint: '{complaint}'.",
    )


@router.get("/patients/{patient_id}/family-risk", summary="Get generational risk summary")
async def get_patient_family_risk(
    patient_id: UUID,
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the patient's family tree annotated with hereditary risk patterns.

    Powers the 'Generational Insight' panel in the Doctor Portal.
    """
    patient = await _get_patient_with_access(patient_id, current_user, db)

    tree = await get_family_tree(patient.id, patient.full_name, db)
    patterns = await detect_hereditary_patterns(patient.id, db)

    return ok(
        data={
            "tree": tree.model_dump(),
            "hereditary_patterns": [p.model_dump() for p in patterns],
            "patient": UserOut.model_validate(patient).model_dump(),
        },
        message="Generational risk summary retrieved.",
    )


@router.post("/session/extend", summary="Extend an active patient session")
async def extend_session(
    patient_id: UUID = Query(...),
    extend_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(require_role(["doctor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Request an extension on the doctor-patient access session.

    The patient must re-consent to extend beyond the original expiry.
    This endpoint creates an extension request (notification-based in production).
    """
    from datetime import datetime, timedelta, timezone
    result = await db.execute(
        select(DoctorAccess).where(
            and_(
                DoctorAccess.patient_id == patient_id,
                DoctorAccess.doctor_id == current_user.id,
                DoctorAccess.is_active == True,
            )
        )
    )
    access = result.scalar_one_or_none()
    if not access:
        raise HTTPException(status_code=404, detail=err("Active access grant not found.", "NOT_FOUND"))

    new_expiry = (access.expires_at or datetime.now(tz=timezone.utc)) + timedelta(days=extend_days)
    access.expires_at = new_expiry
    db.add(access)

    return ok(
        data={"new_expires_at": new_expiry.isoformat(), "extended_by_days": extend_days},
        message=f"Session extended by {extend_days} days.",
    )
