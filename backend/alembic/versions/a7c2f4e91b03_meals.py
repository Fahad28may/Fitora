"""meals and meal items

Revision ID: a7c2f4e91b03
Revises: f3a91c7d2b84
Create Date: 2026-09-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7c2f4e91b03"
down_revision: str | None = "f3a91c7d2b84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_meals_user_id_name", "meals", ["user_id", "name"])

    op.create_table(
        "meal_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "meal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # RESTRICT, matching food_diary_entries: a food referenced by a saved
        # meal must not vanish out from under it.
        sa.Column(
            "food_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("foods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Numeric(7, 2), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
    )
    op.create_index("ix_meal_items_meal_id", "meal_items", ["meal_id"])


def downgrade() -> None:
    op.drop_table("meal_items")
    op.drop_table("meals")
