"""
Family service.

Business logic for:
  - CRUD on family members
  - Invite token generation and account linking
  - Family tree structure building (recursive JSON)
  - Hereditary disease pattern detection across generations
"""

import logging
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.family import FamilyMember
from app.models.health_record import ExtractedEntity, HealthRecord
from app.models.doctor import FamilyInvite
from app.models.user import User
from app.schemas.family import (
    FamilyMemberCreate,
    FamilyMemberUpdate,
    FamilyTreeNode,
    FamilyTreeOut,
    HereditaryPattern,
)

logger = logging.getLogger(__name__)
settings = get_settings()

_INVITE_PREFIX = "invite:"


# ─── CRUD ─────────────────────────────────────────────────────────────────────

async def list_family_members(user_id: UUID, db: AsyncSession) -> List[FamilyMember]:
    """Return all family members belonging to the given user, ordered by creation date."""
    result = await db.execute(
        select(FamilyMember)
        .where(FamilyMember.user_id == user_id)
        .order_by(FamilyMember.created_at)
    )
    return list(result.scalars().all())


async def get_family_member(
    member_id: UUID, user_id: UUID, db: AsyncSession
) -> Optional[FamilyMember]:
    """
    Fetch a single family member by ID, scoped to the requesting user.

    Returns None if not found or if the member belongs to a different user.
    """
    result = await db.execute(
        select(FamilyMember).where(
            and_(FamilyMember.id == member_id, FamilyMember.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def add_family_member(
    user_id: UUID, data: FamilyMemberCreate, db: AsyncSession
) -> FamilyMember:
    """Create and persist a new family member for the given user."""
    member = FamilyMember(
        user_id=user_id,
        name=data.name.strip(),
        relationship=data.relationship,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        is_deceased=data.is_deceased,
        invite_status="not_invited",
    )
    db.add(member)
    await db.flush()
    logger.info("Added family member '%s' for user %s.", member.name, user_id)
    return member


async def update_family_member(
    member: FamilyMember, data: FamilyMemberUpdate, db: AsyncSession
) -> FamilyMember:
    """Apply partial updates to an existing family member record."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(member, field, value)
    db.add(member)
    await db.flush()
    return member


async def delete_family_member(member: FamilyMember, db: AsyncSession) -> None:
    """Delete a family member and cascade-delete their health records."""
    await db.delete(member)
    await db.flush()
    logger.info("Deleted family member %s.", member.id)


# ─── Invites ──────────────────────────────────────────────────────────────────

def _generate_invite_token() -> str:
    """Generate a 32-byte URL-safe random token for family invites."""
    return secrets.token_urlsafe(32)


async def create_invite(
    inviter_id: UUID,
    family_member: FamilyMember,
    invitee_email: Optional[str],
    invitee_phone: Optional[str],
    db: AsyncSession,
    redis: aioredis.Redis,
) -> FamilyInvite:
    """
    Generate and store a family invite token.

    The token is stored in Redis (for fast validation) AND in PostgreSQL
    (for audit trail and persistence across Redis restarts).

    Returns the created FamilyInvite record.
    """
    token = _generate_invite_token()
    expire_hours = settings.INVITE_TOKEN_EXPIRE_HOURS
    expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=expire_hours)

    # Persist invite in PostgreSQL
    invite = FamilyInvite(
        inviter_id=inviter_id,
        family_member_id=family_member.id,
        invitee_email=invitee_email,
        invitee_phone=invitee_phone,
        relationship=family_member.relationship,
        token=token,
        status="pending",
        expires_at=expires_at,
    )
    db.add(invite)

    # Update family member invite status
    family_member.invite_status = "pending"
    family_member.invite_token = token
    family_member.invite_sent_at = datetime.now(tz=timezone.utc)
    db.add(family_member)

    await db.flush()

    # Also cache in Redis for fast lookup (TTL in seconds)
    redis_key = f"{_INVITE_PREFIX}{token}"
    await redis.set(
        redis_key,
        str(inviter_id),
        ex=expire_hours * 3600,
    )

    logger.info(
        "Invite created: inviter=%s → %s (token=%s…).",
        inviter_id,
        invitee_email or invitee_phone,
        token[:8],
    )
    return invite


async def validate_invite_token(
    token: str, db: AsyncSession
) -> Optional[FamilyInvite]:
    """
    Validate a family invite token.

    Checks that the invite exists, is still pending, and has not expired.
    Returns the FamilyInvite ORM object or None if invalid.
    """
    result = await db.execute(
        select(FamilyInvite)
        .where(FamilyInvite.token == token)
        .options(selectinload(FamilyInvite.inviter))
    )
    invite = result.scalar_one_or_none()

    if not invite:
        return None
    if invite.status != "pending":
        return None
    if invite.expires_at and invite.expires_at < datetime.now(tz=timezone.utc):
        invite.status = "expired"
        db.add(invite)
        await db.flush()
        return None

    return invite


async def accept_invite(
    invite: FamilyInvite,
    new_user: User,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> None:
    """
    Link a newly registered user to the inviter's family tree.

    - Sets invite status to 'accepted'
    - Links family_member.related_user_id to the new user
    - Removes the Redis cache key
    """
    invite.status = "accepted"
    invite.responded_at = datetime.now(tz=timezone.utc)
    db.add(invite)

    # Link the family member to the new platform user
    if invite.family_member_id:
        result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == invite.family_member_id)
        )
        member = result.scalar_one_or_none()
        if member:
            member.related_user_id = new_user.id
            member.invite_status = "accepted"
            db.add(member)

    await db.flush()

    # Clean up Redis
    await redis.delete(f"{_INVITE_PREFIX}{invite.token}")
    logger.info(
        "Invite accepted: user %s linked to family tree of %s.",
        new_user.id,
        invite.inviter_id,
    )


# ─── Family Tree ──────────────────────────────────────────────────────────────

async def get_family_tree(user_id: UUID, user_name: str, db: AsyncSession) -> FamilyTreeOut:
    """
    Build the family tree structure for a user.

    For each family member, loads their associated health record entities
    (diseases) to populate the 'conditions' field in the tree node.

    Returns a FamilyTreeOut schema ready for the API response.
    """
    members = await list_family_members(user_id, db)

    nodes: List[FamilyTreeNode] = []
    for member in members:
        # Gather disease entities for this family member
        conditions = await _get_member_conditions(member.id, db)

        nodes.append(
            FamilyTreeNode(
                id=member.id,
                name=member.name,
                relationship=member.relationship,
                gender=member.gender,
                date_of_birth=member.date_of_birth,
                is_deceased=member.is_deceased,
                generation=member.generation,
                is_linked=member.is_linked,
                conditions=conditions,
                risk_contributions=[],
            )
        )

    return FamilyTreeOut(
        user_id=user_id,
        user_name=user_name,
        members=nodes,
        total_members=len(nodes),
    )


async def _get_member_conditions(member_id: UUID, db: AsyncSession) -> List[str]:
    """Return a deduplicated list of disease names linked to a family member."""
    result = await db.execute(
        select(ExtractedEntity.entity_value)
        .join(HealthRecord, HealthRecord.id == ExtractedEntity.record_id)
        .where(
            and_(
                HealthRecord.family_member_id == member_id,
                ExtractedEntity.entity_type == "disease",
            )
        )
        .distinct()
    )
    return [row[0] for row in result.all()]


# ─── Hereditary Pattern Detection ────────────────────────────────────────────

async def detect_hereditary_patterns(
    user_id: UUID, db: AsyncSession
) -> List[HereditaryPattern]:
    """
    Detect hereditary disease patterns across a user's family tree.

    Algorithm:
    1. Load all family members and their disease entities.
    2. Group diseases by name, counting occurrences across generations.
    3. Flag diseases appearing in 2+ members as hereditary patterns.
    4. Compute user risk contribution based on family relationship weights.

    Returns a list of HereditaryPattern objects sorted by risk descending.
    """
    members = await list_family_members(user_id, db)

    # Map: disease_name → list of (member_name, generation)
    disease_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for member in members:
        conditions = await _get_member_conditions(member.id, db)
        for disease in conditions:
            disease_map[disease.lower()].append(
                {
                    "name": member.name,
                    "relationship": member.relationship,
                    "generation": member.generation,
                }
            )

    # Relationship → base risk weight
    RELATIONSHIP_WEIGHTS = {
        "father": 0.35, "mother": 0.35,
        "paternal_grandfather": 0.20, "paternal_grandmother": 0.20,
        "maternal_grandfather": 0.20, "maternal_grandmother": 0.20,
        "brother": 0.15, "sister": 0.15,
        "uncle": 0.10, "aunt": 0.10,
        "cousin": 0.05,
    }

    patterns: List[HereditaryPattern] = []
    for disease, occurrences in disease_map.items():
        if len(occurrences) < 1:
            continue

        affected_members = [o["name"] for o in occurrences]
        generations = {o["generation"] for o in occurrences}

        # Compute cumulative risk from family members
        cumulative_risk = min(
            sum(
                RELATIONSHIP_WEIGHTS.get(o["relationship"], 0.05)
                for o in occurrences
            ),
            0.85,  # Cap at 85%
        )

        risk_level = (
            "high" if cumulative_risk >= 0.5
            else "moderate" if cumulative_risk >= 0.25
            else "low"
        )

        patterns.append(
            HereditaryPattern(
                disease=disease.title(),
                affected_members=affected_members,
                generation_count=len(generations),
                risk_to_user=round(cumulative_risk, 3),
                risk_level=risk_level,
            )
        )

    # Sort by risk descending
    patterns.sort(key=lambda p: p.risk_to_user, reverse=True)
    return patterns
