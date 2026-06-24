"""Initial database schema — all tables.

Revision ID: 001
Revises: (none)
Create Date: 2025-06-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables with constraints, indexes, and foreign keys."""

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("blood_group", sa.String(5), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("profile_image_url", sa.Text(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="patient"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_phone", "users", ["phone"])

    # ── family_members ───────────────────────────────────────────────────────
    op.create_table(
        "family_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("related_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("is_deceased", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("invite_status", sa.String(20), nullable=False, server_default="not_invited"),
        sa.Column("invite_token", sa.String(255), nullable=True),
        sa.Column("invite_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_family_members_user_id", "family_members", ["user_id"])
    op.create_index("ix_family_members_related_user_id", "family_members", ["related_user_id"])
    op.create_unique_constraint("uq_family_invite_token", "family_members", ["invite_token"])

    # ── health_records ───────────────────────────────────────────────────────
    op.create_table(
        "health_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_member_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("source_file_url", sa.Text(), nullable=True),
        sa.Column("source_file_type", sa.String(10), nullable=True),
        sa.Column("source_file_key", sa.String(500), nullable=True),
        sa.Column("extraction_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        sa.Column("structured_data", postgresql.JSONB(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("is_verified_by_user", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_health_records_owner_id", "health_records", ["owner_id"])
    op.create_index("ix_health_records_family_member_id", "health_records", ["family_member_id"])
    op.create_index("ix_health_records_extraction_status", "health_records", ["extraction_status"])
    op.create_index("ix_health_records_created_at", "health_records", ["created_at"])

    # ── extracted_entities ───────────────────────────────────────────────────
    op.create_table(
        "extracted_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("record_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("health_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("icd10_code", sa.String(20), nullable=True),
        sa.Column("atc_code", sa.String(20), nullable=True),
        sa.Column("start_index", sa.Integer(), nullable=True),
        sa.Column("end_index", sa.Integer(), nullable=True),
        sa.Column("user_corrected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_extracted_entities_record_id", "extracted_entities", ["record_id"])

    # ── prescriptions ────────────────────────────────────────────────────────
    op.create_table(
        "prescriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("record_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("health_records.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("diagnosis", sa.String(500), nullable=True),
        sa.Column("icd10_code", sa.String(20), nullable=True),
        sa.Column("doctor_name", sa.String(255), nullable=True),
        sa.Column("doctor_specialization", sa.String(100), nullable=True),
        sa.Column("hospital_name", sa.String(255), nullable=True),
        sa.Column("hospital_address", sa.Text(), nullable=True),
        sa.Column("prescription_date", sa.Date(), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("medicines", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_refillable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("refill_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_prescriptions_owner_id", "prescriptions", ["owner_id"])

    # ── risk_predictions ─────────────────────────────────────────────────────
    op.create_table(
        "risk_predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("disease_name", sa.String(255), nullable=False),
        sa.Column("icd10_code", sa.String(20), nullable=True),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("contributing_factors", postgresql.JSONB(), nullable=True),
        sa.Column("model_version", sa.String(20), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_risk_predictions_user_id", "risk_predictions", ["user_id"])
    op.create_index("ix_risk_predictions_is_active", "risk_predictions", ["is_active"])
    op.create_index("ix_risk_predictions_generated_at", "risk_predictions", ["generated_at"])

    # ── family_invites ───────────────────────────────────────────────────────
    op.create_table(
        "family_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("inviter_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_member_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("family_members.id", ondelete="CASCADE"), nullable=True),
        sa.Column("invitee_email", sa.String(255), nullable=True),
        sa.Column("invitee_phone", sa.String(20), nullable=True),
        sa.Column("relationship", sa.String(50), nullable=True),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_family_invites_token", "family_invites", ["token"])
    op.create_index("ix_family_invites_token", "family_invites", ["token"], unique=True)
    op.create_index("ix_family_invites_invitee_email", "family_invites", ["invitee_email"])

    # ── doctor_access ────────────────────────────────────────────────────────
    op.create_table(
        "doctor_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_level", sa.String(20), nullable=False, server_default="read"),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_doctor_access_patient_id", "doctor_access", ["patient_id"])
    op.create_index("ix_doctor_access_doctor_id", "doctor_access", ["doctor_id"])
    op.create_index("ix_doctor_access_is_active", "doctor_access", ["is_active"])

    # Enable pgcrypto for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("doctor_access")
    op.drop_table("family_invites")
    op.drop_table("risk_predictions")
    op.drop_table("prescriptions")
    op.drop_table("extracted_entities")
    op.drop_table("health_records")
    op.drop_table("family_members")
    op.drop_table("users")
