"""audit events and consent records

Revision ID: f3a91c7d2b84
Revises: b7d4e2a9c1f8
Create Date: 2026-09-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f3a91c7d2b84"
down_revision: str | None = "b7d4e2a9c1f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Both tables use ON DELETE SET NULL rather than CASCADE: they have to
    # outlive the account they describe (that is the point of an audit trail
    # and of a consent record) while ceasing to identify the person.
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_audit_events_user_id_created_at", "audit_events", ["user_id", "created_at"]
    )

    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("consent_type", sa.String(length=32), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_consent_records_user_id_recorded_at",
        "consent_records",
        ["user_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_table("consent_records")
    op.drop_table("audit_events")
