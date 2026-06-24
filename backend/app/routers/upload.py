"""
Upload router.

Endpoints:
  POST /upload    - Upload a file (image/PDF), trigger OCR Celery task
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.schemas.common import ok, err
from app.schemas.health_record import HealthRecordOut
from app.services import record_service

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post(
    "/",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a health document",
)
async def upload_record(
    file: UploadFile = File(..., description="Prescription image or PDF (max 20MB)"),
    record_type: str = Form(default="prescription"),
    family_member_id: Optional[str] = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a health document and trigger the async OCR extraction pipeline.

    **Flow:**
    1. Validate file type and size.
    2. Upload file to S3/MinIO.
    3. Create a HealthRecord row with status='pending'.
    4. Dispatch a Celery task for OCR → NLP extraction.
    5. Return the record ID so the client can poll for completion.

    **Accepted file types:** JPG, PNG, PDF, HEIC (max 20MB)
    """
    # ── Validate file extension ──
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err(
                f"File type '{ext}' is not supported. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
                "UNSUPPORTED_FILE_TYPE",
            ),
        )

    # ── Validate file size ──
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=err(
                f"File is too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB.",
                "FILE_TOO_LARGE",
            ),
        )

    # ── Parse optional family member UUID ──
    fm_id: Optional[UUID] = None
    if family_member_id:
        try:
            fm_id = UUID(family_member_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err("Invalid family_member_id UUID.", "INVALID_UUID"),
            )

    # ── Upload to S3/MinIO ──
    try:
        s3_key, file_url = await record_service.upload_file_to_s3(
            file_bytes=file_bytes,
            original_filename=filename,
            owner_id=current_user.id,
            content_type=file.content_type,
        )
    except Exception as exc:
        logger.exception("S3 upload failed for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=err("File storage service is unavailable. Please try again.", "STORAGE_ERROR"),
        )

    # ── Create HealthRecord with 'pending' status ──
    record = await record_service.create_record(
        owner_id=current_user.id,
        record_type=record_type,
        s3_key=s3_key,
        file_url=file_url,
        file_type=ext,
        family_member_id=fm_id,
        record_date=None,   # Extracted from document by OCR
        db=db,
    )

    # ── Dispatch Celery OCR task (async) ──
    try:
        from app.celery_app import celery_app
        task = celery_app.send_task(
            "app.tasks.ocr_tasks.process_health_record",
            args=[str(record.id), s3_key, ext],
            queue="ocr",
        )
        # Store task ID so the client can poll task status
        record.celery_task_id = task.id
        db.add(record)
        logger.info(
            "OCR task dispatched: record_id=%s task_id=%s", record.id, task.id
        )
    except Exception as exc:
        # Task dispatch failure is non-fatal; record is still created
        logger.warning(
            "Could not dispatch OCR task for record %s: %s. "
            "Manual processing may be required.",
            record.id,
            exc,
        )

    return ok(
        data={
            "record": HealthRecordOut.model_validate(record).model_dump(),
            "task_id": getattr(record, "celery_task_id", None),
            "status": "pending",
            "message": "File uploaded. AI extraction is in progress.",
        },
        message="Upload accepted. Processing will complete shortly.",
    )


@router.get("/status/{task_id}", summary="Poll OCR task status")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Poll the status of an async OCR extraction task.

    Returns the Celery task state: PENDING, STARTED, SUCCESS, FAILURE.
    """
    try:
        from celery.result import AsyncResult
        from app.celery_app import celery_app
        result = AsyncResult(task_id, app=celery_app)
        return ok(
            data={
                "task_id": task_id,
                "state": result.state,
                "info": str(result.info) if result.info else None,
            },
            message=f"Task is {result.state.lower()}.",
        )
    except Exception as exc:
        logger.error("Failed to fetch task status for %s: %s", task_id, exc)
        return ok(
            data={"task_id": task_id, "state": "UNKNOWN"},
            message="Could not fetch task status.",
        )
