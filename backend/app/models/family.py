"""
FamilyMember ORM model.

Represents a family member linked to a user's health profile. A family member
may or may not be a registered platform user themselves (related_user_id is
NULL for non-registered members).
"""

import uuid
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    Date,
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
    from app.models.health_record import HealthRecord
    from app.models.doctor import FamilyInvite


# Valid relationship types between a user and a family member
RELATIONSHIP_TYPES = frozenset([
    "father", "mother", "brother", "sister", "son", "daughter",
    "paternal_grandfather", "paternal_grandmother",
    "maternal_grandfather", "maternal_grandmother",
    "husband", "wife", "partner",
    "uncle", "aunt", "nephew", "niece", "cousin",
    "other",
])

# Generational labels for each relationship type
GENERATION_MAP = {
    "paternal_grandfather": 2,
    "paternal_grandmother": 2,
    "maternal_grandfather": 2,
    "maternal_grandmother": 2,
    "father": 1,
    "mother": 1,
    "uncle": 1,
    "aunt": 1,
    "brother": 0,
    "sister": 0,
    "husband": 0,
    "wife": 0,
    "partner": 0,
    "cousin": 0,
    "son": -1,
    "daughter": -1,
    "nephew": -1,
    "niece": -1,
    "other": 0,
}


class FamilyMember(Base):
    """
    A family member in a user's health tree.

    When a family member accepts an invite and joins the platform, their
    related_user_id is set, enabling bidirectional health data sharing
    (with appropriate consent).
    """

    __tablename__ = "family_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # The platform user who owns this family tree entry
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # If the family member is also a platform user, link them here
    related_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Identity
    name = Column(String(255), nullable=False)
    relationship = Column(String(50), nullable=False)   # e.g. "father", "mother"
    gender = Column(String(10), nullable=True)           # male | female | other
    date_of_birth = Column(Date, nullable=True)
    is_deceased = Column(Boolean, default=False, nullable=False)

    # Invite status for linking their platform account
    invite_status = Column(String(20), default="not_invited", nullable=False)
    # not_invited | pending | accepted | declined | expired
    invite_token = Column(String(255), nullable=True, unique=True)
    invite_sent_at = Column(DateTime(timezone=True), nullable=True)

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
    user: "User" = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="family_members",
    )
    related_user: Optional["User"] = relationship(
        "User",
        foreign_keys=[related_user_id],
    )
    health_records: List["HealthRecord"] = relationship(
        "HealthRecord",
        back_populates="family_member",
        cascade="all, delete-orphan",
        lazy="select",
    )
    invites: List["FamilyInvite"] = relationship(
        "FamilyInvite",
        back_populates="family_member",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<FamilyMember id={self.id} name={self.name} "
            f"relationship={self.relationship}>"
        )

    @property
    def generation(self) -> int:
        """
        Return the generational distance from the user.

        Positive = ancestor, negative = descendant, 0 = same generation.
        """
        return GENERATION_MAP.get(self.relationship, 0)

    @property
    def is_linked(self) -> bool:
        """True if this family member has joined the platform and linked their account."""
        return self.related_user_id is not None
