"""
Health Record service.

Business logic for:
  - Record CRUD and pagination
  - S3/MinIO file upload
  - Celery task dispatch for OCR pipeline
  - Record verification and entity correction
  - Health timeline aggregation
"""

import logging
import mimetypes
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.health_record import ExtractedEntity, HealthRecord
from app.models.family import FamilyMember
from app.schemas.health_record import RecordFilterParams, TimelineEvent, TimelineOut

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── S3 / MinIO ───────────────────────────────────────────────────────────────

def _get_s3_client():
    """
    Return a boto3 S3 client configured for either AWS or local MinIO.

    MinIO uses a custom endpoint URL; AWS uses the default.
    """
    kwargs = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "region_name": settings.AWS_REGION,
    }
    if settings.use_minio:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        kwargs["aws_access_key_id"] = settings.MINIO_ACCESS_KEY
        kwargs["aws_secret_access_key"] = settings.MINIO_SECRET_KEY

    return boto3.client("s3", **kwargs)


def _ensure_bucket_exists(s3_client) -> None:
    """Create the S3/MinIO bucket if it does not already exist."""
    try:
        s3_client.head_bucket(Bucket=settings.AWS_BUCKET_NAME)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("404", "NoSuchBucket"):
            s3_client.create_bucket(Bucket=settings.AWS_BUCKET_NAME)
            logger.info("Created S3 bucket: %s", settings.AWS_BUCKET_NAME)
        else:
            raise


async def upload_file_to_s3(
    file_bytes: bytes,
    original_filename: str,
    owner_id: UUID,
    content_type: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Upload a file to S3/MinIO and return the (object key, presigned URL).

    Args:
        file_bytes:        Raw file content.
        original_filename: Original name of the uploaded file.
        owner_id:          UUID of the file owner (used for S3 prefix).
        content_type:      MIME type (auto-detected if not provided).

    Returns:
        Tuple of (s3_key, presigned_url).
    """
    ext = original_filename.rsplit(".", 1)[-1].lower()
    s3_key = f"records/{owner_id}/{uuid.uuid4()}.{ext}"

    if not content_type:
        content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

    s3 = _get_s3_client()
    _ensure_bucket_exists(s3)

    s3.put_object(
        Bucket=settings.AWS_BUCKET_NAME,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )

    # Generate a presigned URL valid for 1 hour
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=3600,
    )

    logger.info("File uploaded to S3: key=%s", s3_key)
    return s3_key, presigned_url


# ─── Record CRUD ──────────────────────────────────────────────────────────────

async def create_record(
    owner_id: UUID,
    record_type: str,
    s3_key: Optional[str],
    file_url: Optional[str],
    file_type: Optional[str],
    family_member_id: Optional[UUID],
    record_date: Optional[date],
    db: AsyncSession,
) -> HealthRecord:
    """
    Create a HealthRecord row with 'pending' extraction status.

    The OCR pipeline is triggered separately via Celery after this returns.
    """
    record = HealthRecord(
        owner_id=owner_id,
        family_member_id=family_member_id,
        record_type=record_type,
        source_file_url=file_url,
        source_file_key=s3_key,
        source_file_type=file_type,
        extraction_status="pending",
        record_date=record_date,
    )
    record.extracted_entities = []
    db.add(record)
    await db.flush()
    logger.info("Created HealthRecord %s (type=%s) for user %s.", record.id, record_type, owner_id)
    return record


async def get_record(
    record_id: UUID, owner_id: UUID, db: AsyncSession
) -> Optional[HealthRecord]:
    """Fetch a single record by ID, scoped to the owning user."""
    result = await db.execute(
        select(HealthRecord)
        .where(
            and_(
                HealthRecord.id == record_id,
                HealthRecord.owner_id == owner_id,
            )
        )
        .options(selectinload(HealthRecord.extracted_entities))
    )
    return result.scalar_one_or_none()


async def list_records(
    owner_id: UUID,
    params: RecordFilterParams,
    db: AsyncSession,
) -> Tuple[List[HealthRecord], int]:
    """
    List health records with pagination and optional filtering.

    Returns:
        Tuple of (records list, total count matching filters).
    """
    stmt = (
        select(HealthRecord)
        .where(HealthRecord.owner_id == owner_id)
        .options(selectinload(HealthRecord.extracted_entities))
        .order_by(desc(HealthRecord.created_at))
    )

    # Apply filters
    if params.record_type:
        stmt = stmt.where(HealthRecord.record_type == params.record_type)
    if params.family_member_id:
        stmt = stmt.where(HealthRecord.family_member_id == params.family_member_id)
    if params.from_date:
        stmt = stmt.where(HealthRecord.record_date >= params.from_date)
    if params.to_date:
        stmt = stmt.where(HealthRecord.record_date <= params.to_date)
    if not params.include_family:
        stmt = stmt.where(HealthRecord.family_member_id.is_(None))

    # Count total matching (before pagination)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Apply pagination
    offset = (params.page - 1) * params.per_page
    stmt = stmt.offset(offset).limit(params.per_page)

    result = await db.execute(stmt)
    records = list(result.scalars().all())

    return records, total


async def delete_record(record: HealthRecord, db: AsyncSession) -> None:
    """Delete a health record and its associated entities."""
    # 1. Delete associated file from S3 if present
    if record.source_file_key:
        try:
            s3 = _get_s3_client()
            s3.delete_object(Bucket=settings.AWS_BUCKET_NAME, Key=record.source_file_key)
            logger.info("Deleted S3 object: %s", record.source_file_key)
        except Exception as s3_exc:
            logger.warning("Failed to delete S3 object %s: %s", record.source_file_key, s3_exc)

    # 2. Delete MongoDB OCR results
    try:
        from app.database import get_mongo_db
        mongo_db = get_mongo_db()
        await mongo_db["ocr_results"].delete_many({"record_id": str(record.id)})
        logger.info("Deleted MongoDB OCR results for record %s", record.id)
    except Exception as mongo_exc:
        logger.warning("Failed to delete MongoDB OCR results for record %s: %s", record.id, mongo_exc)

    # 3. Delete SQL record
    await db.delete(record)
    await db.flush()
    logger.info("Deleted HealthRecord %s.", record.id)


# ─── Verification ─────────────────────────────────────────────────────────────

async def verify_record(
    record: HealthRecord,
    corrections: Optional[List[Dict[str, Any]]],
    additions: Optional[List[Dict[str, Any]]],
    deletions: Optional[List[str]],
    structured_data: Optional[Dict[str, Any]],
    db: AsyncSession,
) -> HealthRecord:
    """
    Mark a record as user-verified and apply any entity corrections.

    Args:
        record:         The HealthRecord to verify.
        corrections:    List of {entity_id, corrected_value} dicts.
        additions:      List of {entity_type, entity_value} dicts.
        deletions:      List of entity_id strings to delete.
        structured_data: Optional merged structured data override.
        db:             Database session.
    """
    record.is_verified_by_user = True
    record.verified_at = datetime.utcnow()

    if structured_data:
        record.structured_data = {**(record.structured_data or {}), **structured_data}

    # 1. Handle Deletions
    if deletions:
        from sqlalchemy import delete
        deletion_uuids = [UUID(d_id) for d_id in deletions if not d_id.startswith("custom_")]
        if deletion_uuids:
            await db.execute(
                delete(ExtractedEntity).where(
                    and_(
                        ExtractedEntity.id.in_(deletion_uuids),
                        ExtractedEntity.record_id == record.id,
                    )
                )
            )

    # 2. Handle Additions
    if additions:
        for add in additions:
            etype = add.get("entity_type", "other").lower()
            val = add.get("entity_value", "").strip()
            if not val:
                continue

            db_type = etype
            if etype not in ["disease", "medicine", "dosage", "doctor", "hospital", "date", "test_result", "test_name", "symptom", "allergy", "other"]:
                db_type = "other"

            icd10 = None
            atc = None
            if db_type == "disease":
                from ml.utils.medical_constants import ICD10_LOOKUP
                icd10 = ICD10_LOOKUP.get(val.lower())
            elif db_type == "medicine":
                from ml.utils.medical_constants import BRAND_TO_GENERIC, ATC_LOOKUP
                generic = BRAND_TO_GENERIC.get(val.lower(), val.lower())
                atc = ATC_LOOKUP.get(generic, {}).get("atc_code")

            new_entity = ExtractedEntity(
                record_id=record.id,
                entity_type=db_type,
                entity_value=val,
                confidence=1.0,
                icd10_code=icd10,
                atc_code=atc,
                user_corrected=True,
                corrected_value=val,
                corrected_at=datetime.utcnow(),
            )
            db.add(new_entity)

    # 3. Handle Corrections
    if corrections:
        entity_ids = [UUID(c["entity_id"]) for c in corrections]
        entity_result = await db.execute(
            select(ExtractedEntity).where(
                and_(
                    ExtractedEntity.id.in_(entity_ids),
                    ExtractedEntity.record_id == record.id,
                )
            )
        )
        entities = {str(e.id): e for e in entity_result.scalars().all()}

        for correction in corrections:
            entity = entities.get(correction["entity_id"])
            if entity:
                entity.user_corrected = True
                entity.corrected_value = correction["corrected_value"]
                entity.corrected_at = datetime.utcnow()
                db.add(entity)

    # Flush entity edits first so they can be re-queried/synced correctly
    db.add(record)
    await db.flush()

    # 4. Synchronize Prescription Model
    if record.record_type == "prescription":
        from app.models.prescription import Prescription
        p_result = await db.execute(
            select(Prescription).where(Prescription.record_id == record.id)
        )
        prescription = p_result.scalar_one_or_none()
        if not prescription:
            prescription = Prescription(record_id=record.id, owner_id=record.owner_id)
            db.add(prescription)

        # Retrieve all final entities
        ent_result = await db.execute(
            select(ExtractedEntity).where(ExtractedEntity.record_id == record.id)
        )
        all_entities = ent_result.scalars().all()

        diseases = []
        icd10_code = None
        medicines = []

        for ent in all_entities:
            val = ent.corrected_value if ent.user_corrected else ent.entity_value
            etype = ent.entity_type.lower()

            if etype == "disease":
                diseases.append(val)
                if ent.icd10_code and not icd10_code:
                    icd10_code = ent.icd10_code
            elif etype == "medicine":
                medicines.append({
                    "name": val,
                    "atc_code": ent.atc_code,
                })

        prescription.diagnosis = ", ".join(diseases)[:500] if diseases else None
        prescription.icd10_code = icd10_code
        prescription.doctor_name = None       # Not necessary for risk prediction
        prescription.hospital_name = None     # Not necessary for risk prediction
        prescription.medicines = medicines
        db.add(prescription)

    await db.flush()
    logger.info("Record %s verified and synchronized by user.", record.id)
    return record


# ─── Timeline ─────────────────────────────────────────────────────────────────

async def get_health_timeline(user_id: UUID, db: AsyncSession) -> TimelineOut:
    """
    Build a chronological health timeline for a user.

    Includes personal records and (optionally) family member records,
    enriched with their extracted entity chips.
    """
    result = await db.execute(
        select(HealthRecord)
        .where(HealthRecord.owner_id == user_id)
        .options(
            selectinload(HealthRecord.extracted_entities),
            selectinload(HealthRecord.family_member),
        )
        .order_by(desc(HealthRecord.record_date), desc(HealthRecord.created_at))
    )
    records = list(result.scalars().all())

    events: List[TimelineEvent] = []
    for rec in records:
        # Build a human-readable title from record type and primary disease entity
        disease_entities = [
            e for e in rec.extracted_entities if e.entity_type == "disease"
        ]
        primary_disease = disease_entities[0].effective_value.title() if disease_entities else ""
        title = f"{rec.record_type.replace('_', ' ').title()}"
        if primary_disease:
            title += f" — {primary_disease}"

        events.append(
            TimelineEvent(
                record_id=rec.id,
                record_type=rec.record_type,
                record_date=rec.record_date,
                created_at=rec.created_at,
                title=title,
                is_family_record=rec.is_family_record,
                family_member_name=(
                    rec.family_member.name if rec.family_member else None
                ),
                entities=[],  # Populated by router from ORM objects
                extraction_status=rec.extraction_status,
            )
        )

    return TimelineOut(user_id=user_id, events=events, total=len(events))
