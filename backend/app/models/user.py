"""
User ORM model.

Represents a registered platform user — either a patient or a doctor.
All timestamps are stored in UTC.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    Date,
    DateTime,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.family import FamilyMember
    from app.models.health_record import HealthRecord
    from app.models.risk_prediction import RiskPrediction
    from app.models.doctor import DoctorAccess, FamilyInvite


class User(Base):
    """
    Platform user account.

    A user can be a 'patient', 'doctor', or 'admin'. Patients have health
    records, family members, and risk predictions. Doctors have access to
    patients' records (via doctor_access) with explicit patient consent.
    """

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)          # male | female | other
    blood_group = Column(String(5), nullable=True)       # A+, B-, O+, AB+, etc.
    phone = Column(String(20), nullable=True, index=True)
    profile_image_url = Column(Text, nullable=True)
    role = Column(String(20), nullable=False, default="patient")  # patient|doctor|admin

    # Verification
    is_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
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
    family_members: List["FamilyMember"] = relationship(
        "FamilyMember",
        foreign_keys="FamilyMember.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    health_records: List["HealthRecord"] = relationship(
        "HealthRecord",
        foreign_keys="HealthRecord.owner_id",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="select",
    )
    risk_predictions: List["RiskPrediction"] = relationship(
        "RiskPrediction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    # Doctor access grants given BY this user (patient perspective)
    doctor_access_grants: List["DoctorAccess"] = relationship(
        "DoctorAccess",
        foreign_keys="DoctorAccess.patient_id",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="select",
    )
    # Invites sent BY this user
    sent_invites: List["FamilyInvite"] = relationship(
        "FamilyInvite",
        foreign_keys="FamilyInvite.inviter_id",
        back_populates="inviter",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"

    @property
    def is_patient(self) -> bool:
        """True if this user has the patient role."""
        return self.role == "patient"

    @property
    def is_doctor(self) -> bool:
        """True if this user has the doctor role."""
        return self.role == "doctor"

    @property
    def is_admin(self) -> bool:
        """True if this user has the admin role."""
        return self.role == "admin"
