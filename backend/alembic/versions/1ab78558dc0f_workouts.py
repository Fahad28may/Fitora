"""workouts, workout_exercises, workout_sessions, workout_sets

Revision ID: 1ab78558dc0f
Revises: 0f6b97a7e16b
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "1ab78558dc0f"
down_revision: str | None = "0f6b97a7e16b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("workout_type", sa.String(length=16), nullable=False),
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
    op.create_index("ix_workouts_user_id", "workouts", ["user_id"])

    op.create_table(
        "workout_exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workout_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workouts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exercise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exercises.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("target_sets", sa.Integer(), nullable=True),
        sa.Column("target_reps", sa.Integer(), nullable=True),
        sa.Column("target_weight_kg", sa.Numeric(6, 2), nullable=True),
    )
    op.create_index(
        "ix_workout_exercises_workout_id", "workout_exercises", ["workout_id"]
    )

    op.create_table(
        "workout_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workout_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workouts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        "ix_workout_sessions_user_id_started_at",
        "workout_sessions",
        ["user_id", "started_at"],
    )

    op.create_table(
        "workout_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workout_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workout_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exercise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("exercises.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(6, 2), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Numeric(8, 2), nullable=True),
        sa.Column("rest_seconds", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_workout_sets_workout_session_id", "workout_sets", ["workout_session_id"]
    )


def downgrade() -> None:
    op.drop_table("workout_sets")
    op.drop_table("workout_sessions")
    op.drop_table("workout_exercises")
    op.drop_table("workouts")
