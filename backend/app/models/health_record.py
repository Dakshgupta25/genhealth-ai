"""
HealthRecord and ExtractedEntity ORM models.

HealthRecord represents a single uploaded document (prescription, lab report,
etc.) and its OCR/NLP processing state.

ExtractedEntity represents a single piece of information extracted from a
health record by the AI pipeline (disease, medicine, doctor name, etc.).
"""

import uuid
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.family import FamilyMember


# Valid record types
RECORD_TYPES = frozenset([
    "prescription",
    "lab_report",
    "diagnosis",
    "imaging",         # X-ray, MRI, CT
    "discharge_summary",
    "vaccination",
    "other",
])

# Valid extraction statuses
EXTRACTION_STATUSES = frozenset(["pending", "processing", "done", "failed"])

# Valid entity types for extracted data
ENTITY_TYPES = frozenset([
    "disease",
    "medicine",
    "dosage",
    "doctor",
    "hospital",
    "date",
    "test_result",
    "test_name",
    "symptom",
    "allergy",
    "other",
])


class HealthRecord(Base):
    """
    A single health document uploaded by or on behalf of a user.

    The document goes through an async OCR → NLP → entity extraction pipeline.
    Users can review and correct the extracted data. The raw OCR text and
    structured extracted data are stored in separate columns for auditability.
    """

    __tablename__ = "health_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # Ownership: record belongs to a user, optionally for a family member
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    family_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Document classification
    record_type = Column(String(50), nullable=False)       # prescription|lab_report|etc.
    record_date = Column(Date, nullable=True)               # Date on the document

    # Stored file
    source_file_url = Column(Text, nullable=True)           # S3 presigned URL / path
    source_file_type = Column(String(10), nullable=True)    # jpg|png|pdf
    source_file_key = Column(String(500), nullable=True)    # S3 object key

    # OCR/NLP pipeline state
    extraction_status = Column(String(20), default="pending", nullable=False, index=True)
    confidence_score = Column(Float, nullable=True)          # 0.0 – 1.0
    raw_ocr_text = Column(Text, nullable=True)               # Raw OCR output
    structured_data = Column(JSONB, nullable=True)           # Parsed structured output
    celery_task_id = Column(String(255), nullable=True)      # Async task ID for tracking

    # User verification of extracted data
    is_verified_by_user = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ─── Relationships ─────────────────────────────────────────────────
    owner: "User" = relationship(
        "User",
        foreign_keys=[owner_id],
        back_populates="health_records",
    )
    family_member: Optional["FamilyMember"] = relationship(
        "FamilyMember",
        back_populates="health_records",
    )
    extracted_entities: List["ExtractedEntity"] = relationship(
        "ExtractedEntity",
        back_populates="record",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<HealthRecord id={self.id} type={self.record_type} "
            f"status={self.extraction_status}>"
        )

    @property
    def is_family_record(self) -> bool:
        """True if this record was uploaded for a family member, not the owner."""
        return self.family_member_id is not None

    @property
    def confidence_pct(self) -> Optional[float]:
        """Confidence score as a percentage (0–100)."""
        if self.confidence_score is None:
            return None
        return round(self.confidence_score * 100, 1)


class ExtractedEntity(Base):
    """
    A single entity extracted from a HealthRecord by the NLP pipeline.

    Entities include diseases (mapped to ICD-10), medicines (mapped to ATC),
    dosages, doctor names, hospital names, dates, and test results.

    Users can correct AI-extracted values; both the original and corrected
    values are stored for model improvement.
    """

    __tablename__ = "extracted_entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("health_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    entity_type = Column(String(50), nullable=False)     # disease|medicine|dosage|...
    entity_value = Column(Text, nullable=False)           # Raw extracted text

    # Confidence for this specific entity (may differ from record-level confidence)
    confidence = Column(Float, nullable=True)

    # Medical coding
    icd10_code = Column(String(20), nullable=True)        # ICD-10 for diseases
    atc_code = Column(String(20), nullable=True)          # ATC for medicines

    # Source position in OCR text (for highlighting)
    start_index = Column(Integer, nullable=True)
    end_index = Column(Integer, nullable=True)

    # User corrections
    user_corrected = Column(Boolean, default=False, nullable=False)
    corrected_value = Column(Text, nullable=True)
    corrected_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ─── Relationships ─────────────────────────────────────────────────
    record: "HealthRecord" = relationship(
        "HealthRecord",
        back_populates="extracted_entities",
    )

    def __repr__(self) -> str:
        return (
            f"<ExtractedEntity type={self.entity_type} "
            f"value={self.entity_value!r} confidence={self.confidence}>"
        )

    @property
    def effective_value(self) -> str:
        """Return the user-corrected value if available, else the AI-extracted value."""
        return self.corrected_value if self.user_corrected else self.entity_value
