"""profile and goals

Revision ID: 2e9b9f23c1fc
Revises: d1b6e1f99a6c
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "2e9b9f23c1fc"
down_revision: str | None = "d1b6e1f99a6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("sex", sa.String(length=16), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("activity_level", sa.String(length=32), nullable=True),
        sa.Column(
            "unit_system", sa.String(length=16), nullable=False, server_default="metric"
        ),
    )

    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("goal_type", sa.String(length=32), nullable=False),
        sa.Column("intensity", sa.String(length=16), nullable=False),
        sa.Column("target_weight_kg", sa.Numeric(5, 1), nullable=True),
        sa.Column("target_calories", sa.Integer(), nullable=False),
        sa.Column("target_protein_g", sa.Integer(), nullable=False),
        sa.Column("target_carbs_g", sa.Integer(), nullable=False),
        sa.Column("target_fat_g", sa.Integer(), nullable=False),
        sa.Column(
            "target_water_ml", sa.Integer(), nullable=False, server_default="2000"
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_goals_user_id", "goals", ["user_id"])


def downgrade() -> None:
    op.drop_table("goals")
    op.drop_table("user_profiles")
