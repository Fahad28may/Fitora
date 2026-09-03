from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.calorie_service import ActivityLevel, Sex


class UnitSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[Sex | None] = mapped_column(Enum(Sex, native_enum=False, length=16), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    activity_level: Mapped[ActivityLevel | None] = mapped_column(
        Enum(ActivityLevel, native_enum=False, length=32), nullable=True
    )
    unit_system: Mapped[UnitSystem] = mapped_column(
        Enum(UnitSystem, native_enum=False, length=16),
        default=UnitSystem.METRIC,
        nullable=False,
    )
