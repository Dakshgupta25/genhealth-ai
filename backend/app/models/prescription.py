"""
Prescription ORM model.

Represents structured prescription data extracted and verified from
a HealthRecord. Prescriptions are a specialized subset of health records
with structured medicine, dosage, and follow-up fields.
"""

import uuid
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    Date,
    DateTime,
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
    from app.models.health_record import HealthRecord


class Prescription(Base):
    """
    Structured prescription extracted from a health record.

    Linked 1:1 to a HealthRecord of type 'prescription'. Created after
    successful OCR + NLP entity extraction and user verification.
    """

    __tablename__ = "prescriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # Link to the source health record
    record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("health_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Diagnosis
    diagnosis = Column(String(500), nullable=True)
    icd10_code = Column(String(20), nullable=True)

    # Doctor and facility
    doctor_name = Column(String(255), nullable=True)
    doctor_specialization = Column(String(100), nullable=True)
    hospital_name = Column(String(255), nullable=True)
    hospital_address = Column(Text, nullable=True)

    # Prescription date
    prescription_date = Column(Date, nullable=True)
    follow_up_date = Column(Date, nullable=True)

    # Medicines as a JSONB array:
    # [{"name": "Levothyroxine", "dosage": "50mcg", "frequency": "Once daily",
    #   "duration": "3 months", "atc_code": "H03AA01", "instructions": "Morning"}]
    medicines = Column(JSONB, nullable=True, default=list)

    # Additional notes
    notes = Column(Text, nullable=True)
    is_refillable = Column(Boolean, default=False, nullable=False)
    refill_count = Column(Integer, default=0, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ─── Relationships ─────────────────────────────────────────────────
    record: "HealthRecord" = relationship(
        "HealthRecord",
        foreign_keys=[record_id],
    )

    def __repr__(self) -> str:
        return (
            f"<Prescription id={self.id} diagnosis={self.diagnosis!r} "
            f"doctor={self.doctor_name!r}>"
        )

    @property
    def medicine_names(self) -> List[str]:
        """Return a list of medicine names from the JSONB medicines field."""
        if not self.medicines:
            return []
        return [m.get("name", "") for m in self.medicines if m.get("name")]
