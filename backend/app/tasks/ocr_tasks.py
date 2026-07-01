"""
OCR and NLP extraction background tasks for GenHealth AI.
Processes uploaded medical documents asynchronously: S3 Download → OCR → NLP NER → DB Persistence.
"""

import os
import tempfile
import logging
import asyncio
from datetime import datetime, date
from uuid import UUID

import boto3
import numpy as np
from sqlalchemy import select, delete

from app.celery_app import celery_app
from app.config import get_settings
from app.database import get_session_maker, init_mongo, get_mongo_db
from app.models.health_record import HealthRecord, ExtractedEntity
from app.models.prescription import Prescription

from ml.ocr import get_extractor
from ml.nlp.entity_extractor import get_entity_extractor

logger = logging.getLogger(__name__)
settings = get_settings()


def clean_for_mongodb(obj):
    """Recursively convert numpy types to native Python types for MongoDB BSON encoding."""
    if isinstance(obj, dict):
        return {k: clean_for_mongodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_mongodb(x) for x in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return clean_for_mongodb(obj.tolist())
    else:
        return obj


def run_async(coro):
    """Run an async coroutine inside the synchronous Celery task thread."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


def ensure_db_connections():
    """Ensure database connection factories are initialized for the worker process."""
    try:
        get_mongo_db()
    except RuntimeError:
        init_mongo()


def download_file_from_s3(s3_key: str) -> bytes:
    """Download health document from S3/MinIO bucket."""
    kwargs = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "region_name": settings.AWS_REGION,
    }
    if settings.use_minio:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        kwargs["aws_access_key_id"] = settings.MINIO_ACCESS_KEY
        kwargs["aws_secret_access_key"] = settings.MINIO_SECRET_KEY

    s3 = boto3.client("s3", **kwargs)
    response = s3.get_object(Bucket=settings.AWS_BUCKET_NAME, Key=s3_key)
    return response["Body"].read()


async def async_process_health_record(record_id: str, s3_key: str, ext: str) -> bool:
    """Async orchestrator for the OCR → NLP parsing pipeline."""
    ensure_db_connections()
    record_uuid = UUID(record_id)

    async_session = get_session_maker()
    async with async_session() as session:
        # 1. Fetch HealthRecord and update state to 'processing'
        result = await session.execute(select(HealthRecord).where(HealthRecord.id == record_uuid))
        record = result.scalar_one_or_none()
        if not record:
            logger.error("HealthRecord %s not found in database.", record_id)
            return False

        record.extraction_status = "processing"
        await session.commit()

        # Re-fetch inside a clean transaction context
        result = await session.execute(select(HealthRecord).where(HealthRecord.id == record_uuid))
        record = result.scalar_one()

        try:
            logger.info("Downloading file from storage key: %s", s3_key)
            file_bytes = download_file_from_s3(s3_key)

            # 2. Write to temp file on disk for OpenCV/pytesseract processing
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                # 3. Run dual-engine OCR (Tesseract + EasyOCR)
                logger.info("Executing dual-engine OCR on %s...", tmp_path)
                ocr_extractor = get_extractor()
                if ext.lower() == "pdf":
                    ocr_result = ocr_extractor.extract_from_pdf(tmp_path)
                else:
                    ocr_result = ocr_extractor.extract_from_image(tmp_path)
            finally:
                # Ensure clean-up of temporary files
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            raw_text = ocr_result.get("raw_text", "")
            logger.info("OCR completed. Character count: %d", len(raw_text))

            # 4. Extract entities using hybrid MedicalEntityExtractor (Rules + ClinicalBERT)
            logger.info("Running Clinical Entity Extraction...")
            entity_extractor = get_entity_extractor()
            nlp_result = entity_extractor.extract(raw_text)
            
            entities = nlp_result.get("entities", [])
            structured = nlp_result.get("structured_summary", {})

            # 5. Persist extracted entities to PostgreSQL (clean old first for idempotency)
            await session.execute(delete(ExtractedEntity).where(ExtractedEntity.record_id == record_uuid))
            
            for ent in entities:
                raw_type = ent.get("type", "other").lower()

                db_type = raw_type
                if raw_type not in ["disease", "medicine", "dosage", "doctor", "hospital", "date", "test_result", "test_name", "symptom", "allergy", "other"]:
                    db_type = "other"

                db_entity = ExtractedEntity(
                    record_id=record_uuid,
                    entity_type=db_type,
                    entity_value=ent.get("text") or ent.get("normalized") or "",
                    confidence=ent.get("confidence", 1.0),
                    icd10_code=ent.get("icd10_code"),
                    atc_code=ent.get("atc_code"),
                    start_index=ent.get("start"),
                    end_index=ent.get("end"),
                )
                session.add(db_entity)

            # 6. Parse and insert/update Structured Prescription model
            if record.record_type == "prescription":
                logger.info("Populating structured prescription table...")
                
                diagnosis = ", ".join(structured.get("conditions", []))[:500] if structured.get("conditions") else None
                icd10 = None
                for ent in entities:
                    if ent.get("type") == "DISEASE" and ent.get("icd10"):
                        icd10 = ent.get("icd10")
                        break

                # Retrieve first valid date as prescription date
                presc_date = None
                if structured.get("dates"):
                    for d_str in structured.get("dates"):
                        try:
                            presc_date = datetime.strptime(d_str, "%Y-%m-%d").date()
                            break
                        except ValueError:
                            continue

                # Build notes
                notes_lines = []
                if structured.get("allergies"):
                    notes_lines.append("Allergies: " + ", ".join(structured["allergies"]))
                if structured.get("lab_values"):
                    notes_lines.append("Lab observations: " + ", ".join([f"{l['name']}={l['value']}{l['unit']}" for l in structured["lab_values"]]))
                notes = "\n".join(notes_lines) if notes_lines else None

                # Check if Prescription row already exists
                p_result = await session.execute(select(Prescription).where(Prescription.record_id == record_uuid))
                prescription = p_result.scalar_one_or_none()
                if not prescription:
                    prescription = Prescription(record_id=record_uuid, owner_id=record.owner_id)

                # Filter medications to only keep name and atc_code
                raw_meds = structured.get("medications", [])
                filtered_meds = []
                for med in raw_meds:
                    filtered_meds.append({
                        "name": med.get("name"),
                        "atc_code": med.get("atc_code")
                    })

                prescription.diagnosis = diagnosis
                prescription.icd10_code = icd10
                prescription.doctor_name = None       # Not necessary for risk prediction
                prescription.hospital_name = None     # Not necessary for risk prediction
                prescription.prescription_date = presc_date
                prescription.follow_up_date = None    # Not necessary for risk prediction
                prescription.medicines = filtered_meds
                prescription.notes = notes
                
                session.add(prescription)

                # Set record_date in HealthRecord if empty
                if not record.record_date and presc_date:
                    record.record_date = presc_date

            # 7. Update source record status
            record.raw_ocr_text = raw_text
            record.confidence_score = ocr_result.get("overall_confidence", 1.0)
            record.structured_data = structured
            record.extraction_status = "done"
            
            session.add(record)
            await session.commit()
            logger.info("PostgreSQL storage complete for record %s.", record_id)

            # 8. Archive raw document OCR result in MongoDB
            logger.info("Archiving OCR results in MongoDB...")
            mongo_db = get_mongo_db()
            await mongo_db["ocr_results"].update_one(
                {"record_id": record_id},
                {
                    "$set": {
                        "record_id": record_id,
                        "owner_id": str(record.owner_id),
                        "raw_text": raw_text,
                        "words": clean_for_mongodb(ocr_result.get("words", [])),
                        "overall_confidence": float(ocr_result.get("overall_confidence", 1.0)),
                        "processing_time_ms": int(ocr_result.get("processing_time_ms", 0)),
                        "extracted_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )
            logger.info("MongoDB archiving complete.")
            return True

        except Exception as exc:
            logger.exception("OCR Pipeline failed for record %s: %s", record_id, exc)
            record.extraction_status = "failed"
            session.add(record)
            await session.commit()
            return False


@celery_app.task(name="app.tasks.ocr_tasks.process_health_record")
def process_health_record(record_id: str, s3_key: str, ext: str) -> bool:
    """Celery task entry point to process OCR for health records."""
    logger.info("Celery OCR worker triggered: record_id=%s, ext=%s", record_id, ext)
    return run_async(async_process_health_record(record_id, s3_key, ext))
