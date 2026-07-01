"""
HealthRecord and ExtractedEntity Pydantic schemas.
"""

import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class ExtractedEntityOut(BaseModel):
    """Single extracted entity from a health record."""
    id: uuid.UUID
    entity_type: str
    entity_value: str
    effective_value: str
    confidence: Optional[float] = None
    icd10_code: Optional[str] = None
    atc_code: Optional[str] = None
    user_corrected: bool

    model_config = {"from_attributes": True}


class ExtractedEntityCorrect(BaseModel):
    """Schema for user-correcting an extracted entity value."""
    corrected_value: str = Field(..., min_length=1, max_length=500)


class HealthRecordBase(BaseModel):
    """Shared health record fields."""
    record_type: str = Field(..., examples=["prescription", "lab_report"])
    record_date: Optional[date] = None


class HealthRecordOut(HealthRecordBase):
    """Health record as returned in list and detail responses."""
    id: uuid.UUID
    owner_id: uuid.UUID
    family_member_id: Optional[uuid.UUID] = None
    source_file_url: Optional[str] = None
    source_file_type: Optional[str] = None
    extraction_status: str
    confidence_score: Optional[float] = None
    confidence_pct: Optional[float] = None
    is_verified_by_user: bool
    is_family_record: bool
    created_at: datetime
    extracted_entities: List[ExtractedEntityOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RecordVerifyIn(BaseModel):
    """
    Schema for PATCH /records/:id/verify.

    Users can confirm the AI extraction and optionally supply corrections
    as a list of entity corrections.
    """
    corrections: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of {entity_id, corrected_value} dicts",
    )
    additions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of {entity_type, entity_value} dicts for custom additions",
    )
    deletions: Optional[List[str]] = Field(
        default=None,
        description="List of entity_ids to delete",
    )
    structured_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional manually edited structured data to merge",
    )


class RecordFilterParams(BaseModel):
    """Query parameters for GET /records/ (pagination + filtering)."""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    record_type: Optional[str] = None
    family_member_id: Optional[uuid.UUID] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    search: Optional[str] = None         # Free-text search
    include_family: bool = False          # Include family member records


class TimelineEvent(BaseModel):
    """A single event in the health timeline."""
    record_id: uuid.UUID
    record_type: str
    record_date: Optional[date] = None
    created_at: datetime
    title: str                            # Human-readable title
    is_family_record: bool
    family_member_name: Optional[str] = None
    entities: List[ExtractedEntityOut] = Field(default_factory=list)
    extraction_status: str


class TimelineOut(BaseModel):
    """Full health timeline response."""
    user_id: uuid.UUID
    events: List[TimelineEvent]
    total: int
