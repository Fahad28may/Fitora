from enum import StrEnum

from sqlalchemy import JSON, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum_column


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
        str_enum_column(ExerciseDifficulty, 16), nullable=False
    )
    exercise_type: Mapped[ExerciseType] = mapped_column(
        str_enum_column(ExerciseType, 16), nullable=False
    )
