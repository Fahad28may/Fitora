from collections import defaultdict
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_entry import ActivityEntry
from app.models.nutrition import Food, FoodDiaryEntry, FoodNutrition
from app.models.water_entry import WaterEntry
from app.schemas.history import DailyHistoryPoint, HistoryOut
from app.services.nutrition_service import grams_for_quantity, scale_nutrition

DEFAULT_DAYS = 30
MAX_DAYS = 90


class HistoryService:
    """Daily totals over a recent window, for the trend charts in §16.

    One endpoint rather than one per metric: the charts are read together on
    a single screen, and three round trips for three lines on the same axis
    would be worse for both the client and the database.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_history(self, user_id: UUID, days: int = DEFAULT_DAYS) -> HistoryOut:
        today = date.today()
        since = today - timedelta(days=days - 1)

        calories: dict[date, float] = defaultdict(float)
        protein: dict[date, float] = defaultdict(float)
        carbs: dict[date, float] = defaultdict(float)
        fat: dict[date, float] = defaultdict(float)

        diary = await self.db.execute(
            select(FoodDiaryEntry, Food, FoodNutrition)
            .join(Food, Food.id == FoodDiaryEntry.food_id)
            .join(FoodNutrition, FoodNutrition.food_id == Food.id)
            .where(
                FoodDiaryEntry.user_id == user_id,
                FoodDiaryEntry.logged_at >= since,
                FoodDiaryEntry.logged_at <= today,
            )
        )
        for entry, food, nutrition in diary.all():
            # Nutrition is computed on read everywhere else in the app; doing
            # the same here keeps a chart and the diary it summarises from
            # ever disagreeing.
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
            calories[entry.logged_at] += values.calories_kcal
            protein[entry.logged_at] += values.protein_g
            carbs[entry.logged_at] += values.carbs_g
            fat[entry.logged_at] += values.fat_g

        water: dict[date, int] = defaultdict(int)
        water_rows = await self.db.execute(
            select(WaterEntry).where(
                WaterEntry.user_id == user_id,
                WaterEntry.logged_at >= since,
                WaterEntry.logged_at <= today,
            )
        )
        for water_entry in water_rows.scalars().all():
            water[water_entry.logged_at] += water_entry.amount_ml

        activity_minutes: dict[date, int] = defaultdict(int)
        steps: dict[date, int] = defaultdict(int)
        days_with_steps: set[date] = set()
        activity_rows = await self.db.execute(
            select(ActivityEntry).where(
                ActivityEntry.user_id == user_id,
                ActivityEntry.logged_at >= since,
                ActivityEntry.logged_at <= today,
            )
        )
        for activity in activity_rows.scalars().all():
            activity_minutes[activity.logged_at] += activity.duration_min
            if activity.steps is not None:
                steps[activity.logged_at] += activity.steps
                days_with_steps.add(activity.logged_at)

        # Every day in the window is emitted, including empty ones: a chart
        # that silently skips days you logged nothing would compress the
        # timeline and make gaps look like continuity.
        points: list[DailyHistoryPoint] = []
        for offset in range(days):
            day = since + timedelta(days=offset)
            points.append(
                DailyHistoryPoint(
                    date=day,
                    calories_kcal=round(calories[day], 1),
                    protein_g=round(protein[day], 1),
                    carbs_g=round(carbs[day], 1),
                    fat_g=round(fat[day], 1),
                    water_ml=water[day],
                    activity_minutes=activity_minutes[day],
                    # None rather than 0 when nothing reported steps — the
                    # same distinction the dashboard makes.
                    steps=steps[day] if day in days_with_steps else None,
                )
            )

        return HistoryOut(days=days, since=since, points=points)


__all__ = ["DEFAULT_DAYS", "MAX_DAYS", "HistoryService"]
