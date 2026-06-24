"""
Health Records router.

Endpoints:
  GET    /               - List records (paginated + filterable)
  GET    /timeline       - Chronological health timeline
  GET    /entities       - All extracted entities (diseases, medicines)
  GET    /:id            - Get single record detail
  PATCH  /:id/verify     - User confirms/corrects extracted data
  DELETE /:id            - Delete record
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.common import ok, err, PaginationMeta
from app.schemas.health_record import (
    ExtractedEntityOut,
    HealthRecordOut,
    RecordFilterParams,
    RecordVerifyIn,
    TimelineOut,
)
from app.services import record_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", summary="List health records")
async def list_records(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    record_type: str = Query(default=None),
    include_family: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return a paginated list of health records for the authenticated user.

    Use `include_family=true` to also include family member records.
    Filter by `record_type` to narrow results (prescription, lab_report, etc.).
    """
    params = RecordFilterParams(
        page=page,
        per_page=per_page,
        record_type=record_type,
        include_family=include_family,
    )
    records, total = await record_service.list_records(current_user.id, params, db)

    total_pages = max(1, (total + per_page - 1) // per_page)
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
        "data": [HealthRecordOut.model_validate(r).model_dump() for r in records],
        "meta": meta.model_dump(),
        "message": f"{total} record(s) found.",
    }


@router.get("/timeline", summary="Get chronological health timeline")
async def get_timeline(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all health records arranged as a chronological timeline.

    Each event includes the extracted disease/medicine entities for display.
    """
    timeline = await record_service.get_health_timeline(current_user.id, db)
    return ok(data=timeline.model_dump(), message="Timeline retrieved.")


@router.get("/entities", summary="List all extracted entities")
async def list_entities(
    entity_type: str = Query(default=None, description="Filter by type: disease|medicine|..."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all extracted entities across all user health records.

    Optionally filter by entity type (e.g., 'disease', 'medicine').
    Useful for building the disease history list or medicine summary.
    """
    from sqlalchemy import select, and_
    from app.models.health_record import ExtractedEntity, HealthRecord

    stmt = (
        select(ExtractedEntity)
        .join(HealthRecord, HealthRecord.id == ExtractedEntity.record_id)
        .where(HealthRecord.owner_id == current_user.id)
    )
    if entity_type:
        stmt = stmt.where(ExtractedEntity.entity_type == entity_type)

    result = await db.execute(stmt)
    entities = result.scalars().all()

    return ok(
        data=[ExtractedEntityOut.model_validate(e).model_dump() for e in entities],
        message=f"{len(entities)} entities found.",
    )


@router.get("/{record_id}", summary="Get a single health record")
async def get_record(
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a single health record with all extracted entities."""
    record = await record_service.get_record(record_id, current_user.id, db)
    if not record:
        raise HTTPException(status_code=404, detail=err("Record not found.", "NOT_FOUND"))
    return ok(data=HealthRecordOut.model_validate(record).model_dump(), message="Record retrieved.")


@router.patch("/{record_id}/verify", summary="Verify and correct extracted data")
async def verify_record(
    record_id: UUID,
    body: RecordVerifyIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a health record as verified by the user.

    Optionally supply entity corrections (corrected_value per entity_id).
    Corrections are preserved alongside the original AI-extracted values.
    """
    record = await record_service.get_record(record_id, current_user.id, db)
    if not record:
        raise HTTPException(status_code=404, detail=err("Record not found.", "NOT_FOUND"))

    updated = await record_service.verify_record(
        record=record,
        corrections=body.corrections,
        structured_data=body.structured_data,
        db=db,
    )
    return ok(
        data=HealthRecordOut.model_validate(updated).model_dump(),
        message="Record verified and saved.",
    )


@router.delete("/{record_id}", summary="Delete a health record")
async def delete_record(
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a health record and all its extracted entities."""
    record = await record_service.get_record(record_id, current_user.id, db)
    if not record:
        raise HTTPException(status_code=404, detail=err("Record not found.", "NOT_FOUND"))

    await record_service.delete_record(record, db)
    return ok(message="Record deleted.")
