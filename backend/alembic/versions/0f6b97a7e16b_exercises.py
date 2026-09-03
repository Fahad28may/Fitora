"""exercises

Revision ID: 0f6b97a7e16b
Revises: 100181378c48
Create Date: 2026-09-03

"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.seed_data import SEED_EXERCISES

revision: str = "0f6b97a7e16b"
down_revision: str | None = "100181378c48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_exercises_table = sa.table(
    "exercises",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.String),
    sa.column("muscle_groups", sa.JSON),
    sa.column("equipment", sa.String),
    sa.column("instructions", sa.Text),
    sa.column("difficulty", sa.String),
    sa.column("exercise_type", sa.String),
)


def upgrade() -> None:
    op.create_table(
        "exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("muscle_groups", sa.JSON(), nullable=False),
        sa.Column("equipment", sa.String(length=60), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("exercise_type", sa.String(length=16), nullable=False),
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
    op.create_index("ix_exercises_name", "exercises", ["name"])

    op.bulk_insert(
        _exercises_table,
        [
            {
                "id": uuid.uuid4(),
                "name": row[0],
                "muscle_groups": row[1],
                "equipment": row[2],
                "instructions": row[3],
                "difficulty": row[4],
                "exercise_type": row[5],
            }
            for row in SEED_EXERCISES
        ],
    )


def downgrade() -> None:
    op.drop_table("exercises")
