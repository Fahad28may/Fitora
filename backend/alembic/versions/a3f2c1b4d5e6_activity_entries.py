"""activity entries

Revision ID: a3f2c1b4d5e6
Revises: c0cc4c9f9463
Create Date: 2026-09-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a3f2c1b4d5e6"
down_revision: str | None = "c0cc4c9f9463"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activity_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("logged_at", sa.Date(), nullable=False),
        sa.Column("activity_type", sa.String(length=16), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Numeric(6, 2), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("calories_burned", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_activity_entries_user_id_logged_at",
        "activity_entries",
        ["user_id", "logged_at"],
    )


def downgrade() -> None:
    op.drop_table("activity_entries")
