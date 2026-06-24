"""
Family Pydantic schemas.

Request/response models for family member CRUD, family tree structure,
invite sending, and hereditary risk pattern endpoints.
"""

import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, EmailStr, Field


class FamilyMemberBase(BaseModel):
    """Shared fields for family member schemas."""
    name: str = Field(..., min_length=1, max_length=255)
    relationship: str = Field(..., examples=["father", "mother", "paternal_grandfather"])
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    date_of_birth: Optional[date] = None
    is_deceased: bool = False


class FamilyMemberCreate(FamilyMemberBase):
    """Schema for POST /family/members."""
    pass


class FamilyMemberUpdate(BaseModel):
    """Schema for PATCH /family/members/:id — all fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    relationship: Optional[str] = None
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    date_of_birth: Optional[date] = None
    is_deceased: Optional[bool] = None


class FamilyMemberOut(FamilyMemberBase):
    """Family member as returned in API responses."""
    id: uuid.UUID
    user_id: uuid.UUID
    related_user_id: Optional[uuid.UUID] = None
    invite_status: str
    is_linked: bool
    generation: int
    created_at: datetime

    model_config = {"from_attributes": True}


class FamilyInviteCreate(BaseModel):
    """Schema for POST /family/invite."""
    family_member_id: uuid.UUID
    invitee_email: Optional[EmailStr] = None
    invitee_phone: Optional[str] = Field(None, max_length=20)

    model_config = {"json_schema_extra": {
        "example": {
            "family_member_id": "550e8400-e29b-41d4-a716-446655440000",
            "invitee_email": "father@example.com",
        }
    }}


class FamilyInviteOut(BaseModel):
    """Invite response returned after sending an invite."""
    id: uuid.UUID
    family_member_id: uuid.UUID
    invitee_email: Optional[str] = None
    invitee_phone: Optional[str] = None
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteAcceptIn(BaseModel):
    """Schema for POST /invite/:token/accept."""
    # Invitee creates an account or logs in via this endpoint
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None


class FamilyTreeNode(BaseModel):
    """A single node in the family tree JSON structure."""
    id: uuid.UUID
    name: str
    relationship: str
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    is_deceased: bool
    generation: int
    is_linked: bool
    conditions: List[str] = Field(default_factory=list, description="Known diseases/conditions")
    risk_contributions: List[Dict[str, Any]] = Field(default_factory=list)


class FamilyTreeOut(BaseModel):
    """Full family tree response."""
    user_id: uuid.UUID
    user_name: str
    members: List[FamilyTreeNode]
    total_members: int


class HereditaryPattern(BaseModel):
    """A hereditary disease pattern detected across generations."""
    disease: str
    icd10_code: Optional[str] = None
    affected_members: List[str]
    generation_count: int
    risk_to_user: float
    risk_level: str


class HereditaryPatternsOut(BaseModel):
    """Response for GET /family/shared-risks."""
    patterns: List[HereditaryPattern]
    user_id: uuid.UUID
    total_patterns: int
