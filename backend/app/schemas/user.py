"""
User Pydantic schemas.

Request/response models for the user registration, login, profile update,
and auth token endpoints.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Shared fields for user schemas."""
    full_name: str = Field(..., min_length=2, max_length=255, examples=["Aryan Sharma"])
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20, examples=["+91-9876543210"])


class UserCreate(UserBase):
    """Schema for POST /auth/signup."""
    password: str = Field(..., min_length=8, max_length=128)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    blood_group: Optional[str] = Field(None, max_length=5, examples=["B+"])
    role: str = Field(default="patient", pattern="^(patient|doctor)$")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce minimum password complexity."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserLogin(BaseModel):
    """Schema for POST /auth/login."""
    email: EmailStr
    password: str

    model_config = {"json_schema_extra": {
        "example": {"email": "aryan@example.com", "password": "SecurePass1"}
    }}


class UserUpdate(BaseModel):
    """Schema for PATCH /auth/me — all fields optional."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    blood_group: Optional[str] = Field(None, max_length=5)
    profile_image_url: Optional[str] = None


class UserOut(BaseModel):
    """Schema for user data returned in API responses."""
    id: uuid.UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    profile_image_url: Optional[str] = None
    role: str
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    """JWT token pair returned after login or refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class RefreshTokenIn(BaseModel):
    """Body for POST /auth/refresh."""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Body for POST /auth/forgot-password."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Body for POST /auth/reset-password."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class OTPVerify(BaseModel):
    """Body for POST /auth/verify-email."""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
