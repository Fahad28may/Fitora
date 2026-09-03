"""nutrition: foods, food_nutrition, food_diary_entries

Revision ID: e258c6749379
Revises: 26e6d7fdefc1
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e258c6749379"
down_revision: str | None = "26e6d7fdefc1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "foods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("serving_description", sa.String(length=120), nullable=False),
        sa.Column("serving_grams", sa.Numeric(7, 2), nullable=True),
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
    op.create_index("ix_foods_name", "foods", ["name"])
    op.create_index("ix_foods_owner_user_id", "foods", ["owner_user_id"])
    op.create_index("ix_foods_barcode", "foods", ["barcode"])

    op.create_table(
        "food_nutrition",
        sa.Column(
            "food_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("foods.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("per_grams", sa.Numeric(7, 2), nullable=False),
        sa.Column("calories_kcal", sa.Numeric(7, 2), nullable=False),
        sa.Column("protein_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("carbs_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("fat_g", sa.Numeric(6, 2), nullable=False),
        sa.Column("fiber_g", sa.Numeric(6, 2), nullable=True),
    )

    op.create_table(
        "food_diary_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "food_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("foods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("logged_at", sa.Date(), nullable=False),
        sa.Column("meal_category", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Numeric(7, 2), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column(
            "created_via_ai", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("ai_confidence", sa.Integer(), nullable=True),
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
        "ix_food_diary_entries_user_id_logged_at",
        "food_diary_entries",
        ["user_id", "logged_at"],
    )


def downgrade() -> None:
    op.drop_table("food_diary_entries")
    op.drop_table("food_nutrition")
    op.drop_table("foods")
