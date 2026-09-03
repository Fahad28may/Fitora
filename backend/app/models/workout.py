from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkoutType(StrEnum):
    SINGLE = "single"
    ROUTINE = "routine"
    PROGRAM = "program"


class Workout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workouts"
    __table_args__ = (Index("ix_workouts_user_id", "user_id"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    workout_type: Mapped[WorkoutType] = mapped_column(
        Enum(WorkoutType, native_enum=False, length=16), nullable=False
    )


class WorkoutExercise(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workout_exercises"
    __table_args__ = (Index("ix_workout_exercises_workout_id", "workout_id"),)

    workout_id: Mapped[UUID] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    target_sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)


class WorkoutSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workout_sessions"
    __table_args__ = (Index("ix_workout_sessions_user_id_started_at", "user_id", "started_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workout_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workouts.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkoutSet(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workout_sets"
    __table_args__ = (Index("ix_workout_sets_workout_session_id", "workout_session_id"),)

    workout_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
