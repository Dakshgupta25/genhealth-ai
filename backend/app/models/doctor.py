"""
DoctorAccess and FamilyInvite ORM models.

DoctorAccess: Time-limited, consent-based access granted by a patient to a
doctor. Enables the Doctor Portal to view patient health records.

FamilyInvite: Invite tokens sent to family members to join the platform and
link their health data to the inviter's family tree.
"""

import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.family import FamilyMember


class DoctorAccess(Base):
    """
    Patient-granted access for a doctor to view their health records.

    Access is time-limited, level-based (read-only by default), and can be
    revoked at any time by the patient. Every grant and revocation is logged
    for auditing purposes (consent_text captures the exact consent given).
    """

    __tablename__ = "doctor_access"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    access_level = Column(String(20), default="read", nullable=False)
    # read | write | full

    granted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Consent audit trail
    consent_text = Column(Text, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(Text, nullable=True)

    # ─── Relationships ─────────────────────────────────────────────────
    patient: "User" = relationship(
        "User",
        foreign_keys=[patient_id],
        back_populates="doctor_access_grants",
    )
    doctor: "User" = relationship(
        "User",
        foreign_keys=[doctor_id],
    )

    def __repr__(self) -> str:
        return (
            f"<DoctorAccess patient={self.patient_id} "
            f"doctor={self.doctor_id} active={self.is_active}>"
        )


class FamilyInvite(Base):
    """
    Invitation sent to a family member to join the platform.

    Contains a unique token that is emailed or SMSed to the invitee. When
    accepted, the invitee's new account is linked to the inviter's family
    tree entry. Tokens expire after INVITE_TOKEN_EXPIRE_HOURS hours.
    """

    __tablename__ = "family_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    inviter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    family_member_id = Column(
        UUID(as_uuid=True),
        ForeignKey("family_members.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    invitee_email = Column(String(255), nullable=True, index=True)
    invitee_phone = Column(String(20), nullable=True)

    relationship = Column(String(50), nullable=True)
    token = Column(String(255), unique=True, nullable=False, index=True)

    status = Column(String(20), default="pending", nullable=False)
    # pending | accepted | declined | expired

    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # ─── Relationships ─────────────────────────────────────────────────
    inviter: "User" = relationship(
        "User",
        foreign_keys=[inviter_id],
        back_populates="sent_invites",
    )
    family_member: Optional["FamilyMember"] = relationship(
        "FamilyMember",
        back_populates="invites",
    )

    def __repr__(self) -> str:
        return (
            f"<FamilyInvite inviter={self.inviter_id} "
            f"to={self.invitee_email or self.invitee_phone} "
            f"status={self.status}>"
        )
