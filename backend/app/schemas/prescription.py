"""Prescription Pydantic schemas."""

import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class MedicineItem(BaseModel):
    """A single medicine entry in a prescription."""
    name: str
    dosage: Optional[str] = None          # e.g. "50mcg"
    frequency: Optional[str] = None       # e.g. "Once daily"
    duration: Optional[str] = None        # e.g. "3 months"
    instructions: Optional[str] = None    # e.g. "Take on empty stomach"
    atc_code: Optional[str] = None


class PrescriptionOut(BaseModel):
    """Prescription as returned in API responses."""
    id: uuid.UUID
    record_id: uuid.UUID
    owner_id: uuid.UUID
    diagnosis: Optional[str] = None
    icd10_code: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None
    prescription_date: Optional[date] = None
    follow_up_date: Optional[date] = None
    medicines: List[MedicineItem] = Field(default_factory=list)
    medicine_names: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    is_refillable: bool
    refill_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
