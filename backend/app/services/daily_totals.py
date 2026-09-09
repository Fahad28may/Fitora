"""Per-day totals over a date window, shared by the charts and the analytics.

Extracted from `HistoryService` so the trend charts (§16) and the analytics
summary read the *same* numbers from the *same* three queries. Two independent
aggregations over the same rows would eventually disagree, and a chart that
disagrees with the summary printed beside it is worse than either alone.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_entry import ActivityEntry
from app.models.nutrition import Food, FoodDiaryEntry, FoodNutrition
from app.models.water_entry import WaterEntry
from app.services.nutrition_service import grams_for_quantity, scale_nutrition


@dataclass
class DailyTotals:
    """Totals keyed by day. Missing keys mean "nothing logged", which the
    `*_days` sets make explicit — callers must not read a 0 from a defaultdict
    as evidence the user logged a zero."""

    calories: dict[date, float] = field(default_factory=lambda: defaultdict(float))
    protein: dict[date, float] = field(default_factory=lambda: defaultdict(float))
    carbs: dict[date, float] = field(default_factory=lambda: defaultdict(float))
    fat: dict[date, float] = field(default_factory=lambda: defaultdict(float))
    water_ml: dict[date, int] = field(default_factory=lambda: defaultdict(int))
    activity_minutes: dict[date, int] = field(default_factory=lambda: defaultdict(int))
    steps: dict[date, int] = field(default_factory=lambda: defaultdict(int))
    activity_burn_kcal: dict[date, int] = field(default_factory=lambda: defaultdict(int))

    food_days: set[date] = field(default_factory=set)
    water_days: set[date] = field(default_factory=set)
    activity_days: set[date] = field(default_factory=set)
    step_days: set[date] = field(default_factory=set)
    burn_days: set[date] = field(default_factory=set)


async def collect_daily_totals(
    db: AsyncSession, user_id: UUID, *, since: date, until: date
) -> DailyTotals:
    """Aggregate one user's food, water, and activity between two dates."""
    totals = DailyTotals()

    diary = await db.execute(
        select(FoodDiaryEntry, Food, FoodNutrition)
        .join(Food, Food.id == FoodDiaryEntry.food_id)
        .join(FoodNutrition, FoodNutrition.food_id == Food.id)
        .where(
            FoodDiaryEntry.user_id == user_id,
            FoodDiaryEntry.logged_at >= since,
            FoodDiaryEntry.logged_at <= until,
        )
    )
    for entry, food, nutrition in diary.all():
        # Nutrition is computed on read everywhere else in the app; doing the
        # same here keeps a summary and the diary it summarises from ever
        # disagreeing.
        grams = grams_for_quantity(
            quantity=float(entry.quantity),
            unit=entry.unit,
            serving_grams=(
                float(food.serving_grams) if food.serving_grams is not None else None
            ),
        )
        values = scale_nutrition(
            per_grams=float(nutrition.per_grams),
            calories_kcal=float(nutrition.calories_kcal),
            protein_g=float(nutrition.protein_g),
            carbs_g=float(nutrition.carbs_g),
            fat_g=float(nutrition.fat_g),
            fiber_g=None,
            grams=grams,
        )
        totals.calories[entry.logged_at] += values.calories_kcal
        totals.protein[entry.logged_at] += values.protein_g
        totals.carbs[entry.logged_at] += values.carbs_g
        totals.fat[entry.logged_at] += values.fat_g
        totals.food_days.add(entry.logged_at)

    water_rows = await db.execute(
        select(WaterEntry).where(
            WaterEntry.user_id == user_id,
            WaterEntry.logged_at >= since,
            WaterEntry.logged_at <= until,
        )
    )
    for water_entry in water_rows.scalars().all():
        totals.water_ml[water_entry.logged_at] += water_entry.amount_ml
        totals.water_days.add(water_entry.logged_at)

    activity_rows = await db.execute(
        select(ActivityEntry).where(
            ActivityEntry.user_id == user_id,
            ActivityEntry.logged_at >= since,
            ActivityEntry.logged_at <= until,
        )
    )
    for activity in activity_rows.scalars().all():
        totals.activity_minutes[activity.logged_at] += activity.duration_min
        totals.activity_days.add(activity.logged_at)
        if activity.steps is not None:
            totals.steps[activity.logged_at] += activity.steps
            totals.step_days.add(activity.logged_at)
        if activity.calories_burned is not None:
            totals.activity_burn_kcal[activity.logged_at] += activity.calories_burned
            totals.burn_days.add(activity.logged_at)

    return totals


__all__ = ["DailyTotals", "collect_daily_totals"]
