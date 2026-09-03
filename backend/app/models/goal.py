from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.services.calorie_service import GoalIntensity, GoalType


class Goal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goals"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    goal_type: Mapped[GoalType] = mapped_column(
        Enum(GoalType, native_enum=False, length=32), nullable=False
    )
    intensity: Mapped[GoalIntensity] = mapped_column(
        Enum(GoalIntensity, native_enum=False, length=16), nullable=False
    )
    target_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)

    target_calories: Mapped[int] = mapped_column(Integer, nullable=False)
    target_protein_g: Mapped[int] = mapped_column(Integer, nullable=False)
    target_carbs_g: Mapped[int] = mapped_column(Integer, nullable=False)
    target_fat_g: Mapped[int] = mapped_column(Integer, nullable=False)
    target_water_ml: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
