from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FoodSource(StrEnum):
    SYSTEM = "system"
    USER = "user"
    EXTERNAL_DB = "external_db"


class MealCategory(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class LogUnit(StrEnum):
    SERVING = "serving"
    GRAM = "gram"


class LogSource(StrEnum):
    SEARCH = "search"
    MANUAL = "manual"
    BARCODE = "barcode"
    NATURAL_LANGUAGE = "natural_language"
    PHOTO = "photo"


class Food(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "foods"
    __table_args__ = (Index("ix_foods_name", "name"),)

    source: Mapped[FoodSource] = mapped_column(
        Enum(FoodSource, native_enum=False, length=16), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    serving_description: Mapped[str] = mapped_column(String(120), nullable=False)
    serving_grams: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)


class FoodNutrition(Base):
    __tablename__ = "food_nutrition"

    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"), primary_key=True
    )
    per_grams: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    calories_kcal: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    protein_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    carbs_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    fat_g: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    fiber_g: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)


class FoodDiaryEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "food_diary_entries"
    __table_args__ = (
        Index("ix_food_diary_entries_user_id_logged_at", "user_id", "logged_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("foods.id", ondelete="RESTRICT"), nullable=False
    )
    logged_at: Mapped[date] = mapped_column(Date, nullable=False)
    meal_category: Mapped[MealCategory] = mapped_column(
        Enum(MealCategory, native_enum=False, length=16), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    unit: Mapped[LogUnit] = mapped_column(
        Enum(LogUnit, native_enum=False, length=16), nullable=False
    )
    source: Mapped[LogSource] = mapped_column(
        Enum(LogSource, native_enum=False, length=24), nullable=False
    )
    created_via_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
