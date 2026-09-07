from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum_column
from app.models.nutrition import LogUnit


class Meal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A reusable set of foods the user eats together — "My Breakfast" (§5).

    A template, not a log: saving a meal records nothing in the diary. Logging
    it expands into one `food_diary_entries` row per item, so a logged meal is
    editable afterwards exactly like anything else the user logged, and later
    edits to the template do not rewrite history.
    """

    __tablename__ = "meals"
    __table_args__ = (Index("ix_meals_user_id_name", "user_id", "name"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class MealItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "meal_items"
    __table_args__ = (Index("ix_meal_items_meal_id", "meal_id"),)

    meal_id: Mapped[UUID] = mapped_column(
        ForeignKey("meals.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT, matching food_diary_entries: a food referenced by a saved meal
    # must not vanish out from under it.
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("foods.id", ondelete="RESTRICT"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    unit: Mapped[LogUnit] = mapped_column(str_enum_column(LogUnit, 16), nullable=False)
