from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition import Food, FoodDiaryEntry, FoodNutrition
from app.repositories.nutrition_repository import FoodDiaryRepository, FoodRepository
from app.schemas.nutrition import FoodDiaryEntryOut
from app.services.nutrition_service import (
    MissingServingSizeError,
    grams_for_quantity,
    scale_nutrition,
)


class FoodNotFoundError(Exception):
    pass


class FoodNotAccessibleError(Exception):
    pass


def _entry_to_out(entry: FoodDiaryEntry, food: Food, nutrition: FoodNutrition) -> FoodDiaryEntryOut:
    grams = grams_for_quantity(
        quantity=float(entry.quantity),
        unit=entry.unit,
        serving_grams=float(food.serving_grams) if food.serving_grams is not None else None,
    )
    values = scale_nutrition(
        per_grams=float(nutrition.per_grams),
        calories_kcal=float(nutrition.calories_kcal),
        protein_g=float(nutrition.protein_g),
        carbs_g=float(nutrition.carbs_g),
        fat_g=float(nutrition.fat_g),
        fiber_g=float(nutrition.fiber_g) if nutrition.fiber_g is not None else None,
        grams=grams,
    )
    return FoodDiaryEntryOut(
        id=entry.id,
        food_id=food.id,
        food_name=food.name,
        logged_at=entry.logged_at,
        meal_category=entry.meal_category,
        quantity=float(entry.quantity),
        unit=entry.unit,
        source=entry.source,
        calories_kcal=values.calories_kcal,
        protein_g=values.protein_g,
        carbs_g=values.carbs_g,
        fat_g=values.fat_g,
        fiber_g=values.fiber_g,
        created_at=entry.created_at,
    )


class FoodDiaryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.foods = FoodRepository(db)
        self.diary = FoodDiaryRepository(db)

    async def create_entry(
        self,
        *,
        user_id: UUID,
        food_id: UUID,
        logged_at: date,
        meal_category: str,
        quantity: float,
        unit: str,
        source: str,
    ) -> FoodDiaryEntryOut:
        found = await self.foods.get_with_nutrition(food_id)
        if found is None:
            raise FoodNotFoundError
        food, nutrition = found
        if not await self.foods.is_readable_by(food, user_id):
            raise FoodNotAccessibleError

        # Fail fast with a clear error rather than persisting an entry whose
        # nutrition can never be computed.
        grams_for_quantity(
            quantity=quantity,
            unit=unit,  # type: ignore[arg-type]
            serving_grams=float(food.serving_grams) if food.serving_grams is not None else None,
        )

        entry = await self.diary.create_entry(
            user_id=user_id,
            food_id=food_id,
            logged_at=logged_at,
            meal_category=meal_category,
            quantity=quantity,
            unit=unit,
            source=source,
        )
        await self.db.commit()
        return _entry_to_out(entry, food, nutrition)

    async def list_for_day(self, user_id: UUID, logged_at: date) -> list[FoodDiaryEntryOut]:
        rows = await self.diary.list_for_day(user_id, logged_at)
        return [_entry_to_out(entry, food, nutrition) for entry, food, nutrition in rows]


__all__ = [
    "FoodDiaryService",
    "FoodNotAccessibleError",
    "FoodNotFoundError",
    "MissingServingSizeError",
]
