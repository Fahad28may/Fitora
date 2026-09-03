from enum import StrEnum

from sqlalchemy import JSON, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExerciseType(StrEnum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    FLEXIBILITY = "flexibility"
    BALANCE = "balance"


class ExerciseDifficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Exercise(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercises"
    __table_args__ = (Index("ix_exercises_name", "name"),)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    muscle_groups: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    equipment: Mapped[str | None] = mapped_column(String(60), nullable=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[ExerciseDifficulty] = mapped_column(
        Enum(ExerciseDifficulty, native_enum=False, length=16), nullable=False
    )
    exercise_type: Mapped[ExerciseType] = mapped_column(
        Enum(ExerciseType, native_enum=False, length=16), nullable=False
    )
