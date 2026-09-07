from datetime import date
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meal import Meal, MealItem
from app.models.nutrition import Food, FoodNutrition, LogSource, MealCategory
from app.repositories.nutrition_repository import FoodDiaryRepository, FoodRepository
from app.schemas.meal import MealItemOut, MealOut
from app.schemas.nutrition import FoodDiaryEntryOut
from app.services.food_diary_service import _entry_to_out
from app.services.nutrition_service import grams_for_quantity, scale_nutrition


class MealNotFoundError(Exception):
    pass


class MealFoodNotAccessibleError(Exception):
    """A meal referenced a food the user cannot read — someone else's custom
    food, or one that does not exist."""

    def __init__(self, food_id: UUID) -> None:
        super().__init__(str(food_id))
        self.food_id = food_id


class MealService:
    """Reusable meal templates (§5 "Custom meals").

    Logging a meal expands it into ordinary diary entries rather than storing
    a reference to the template. That keeps a logged meal editable line by line
    afterwards, and means editing "My Breakfast" tomorrow does not silently
    rewrite what the user ate last week.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.foods = FoodRepository(db)
        self.diary = FoodDiaryRepository(db)

    async def _load_items(self, meal_id: UUID) -> list[tuple[MealItem, Food, FoodNutrition]]:
        result = await self.db.execute(
            select(MealItem, Food, FoodNutrition)
            .join(Food, Food.id == MealItem.food_id)
            .join(FoodNutrition, FoodNutrition.food_id == Food.id)
            .where(MealItem.meal_id == meal_id)
            .order_by(MealItem.order_index)
        )
        return [(row[0], row[1], row[2]) for row in result.all()]

    def _to_out(
        self, meal: Meal, rows: list[tuple[MealItem, Food, FoodNutrition]]
    ) -> MealOut:
        items: list[MealItemOut] = []
        totals = {"calories_kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
        for item, food, nutrition in rows:
            grams = grams_for_quantity(
                quantity=float(item.quantity),
                unit=item.unit,
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
                fiber_g=float(nutrition.fiber_g) if nutrition.fiber_g is not None else None,
                grams=grams,
            )
            items.append(
                MealItemOut(
                    id=item.id,
                    food_id=food.id,
                    food_name=food.name,
                    quantity=float(item.quantity),
                    unit=item.unit,
                    calories_kcal=values.calories_kcal,
                    protein_g=values.protein_g,
                    carbs_g=values.carbs_g,
                    fat_g=values.fat_g,
                )
            )
            totals["calories_kcal"] += values.calories_kcal
            totals["protein_g"] += values.protein_g
            totals["carbs_g"] += values.carbs_g
            totals["fat_g"] += values.fat_g

        return MealOut(
            id=meal.id,
            name=meal.name,
            created_at=meal.created_at,
            items=items,
            total_calories_kcal=round(totals["calories_kcal"], 1),
            total_protein_g=round(totals["protein_g"], 1),
            total_carbs_g=round(totals["carbs_g"], 1),
            total_fat_g=round(totals["fat_g"], 1),
        )

    async def create(
        self,
        *,
        user_id: UUID,
        name: str,
        items: list[tuple[UUID, float, str]],
    ) -> MealOut:
        # Every referenced food is ownership-checked up front, so a meal can
        # never become a way to read someone else's custom food's nutrition.
        for food_id, quantity, unit in items:
            found = await self.foods.get_with_nutrition(food_id)
            if found is None or not await self.foods.is_readable_by(found[0], user_id):
                raise MealFoodNotAccessibleError(food_id)
            # Fail now rather than at log time if the quantity can never be
            # converted to grams (a serving-based quantity on a food with no
            # serving size).
            grams_for_quantity(
                quantity=quantity,
                unit=unit,  # type: ignore[arg-type]
                serving_grams=(
                    float(found[0].serving_grams)
                    if found[0].serving_grams is not None
                    else None
                ),
            )

        meal = Meal(user_id=user_id, name=name)
        self.db.add(meal)
        await self.db.flush()
        for index, (food_id, quantity, unit) in enumerate(items):
            self.db.add(
                MealItem(
                    meal_id=meal.id,
                    food_id=food_id,
                    order_index=index,
                    quantity=quantity,
                    unit=unit,
                )
            )
        await self.db.flush()
        await self.db.commit()
        return self._to_out(meal, await self._load_items(meal.id))

    async def list_for_user(self, user_id: UUID) -> list[MealOut]:
        result = await self.db.execute(
            select(Meal).where(Meal.user_id == user_id).order_by(Meal.name)
        )
        return [
            self._to_out(meal, await self._load_items(meal.id))
            for meal in result.scalars().all()
        ]

    async def get(self, *, user_id: UUID, meal_id: UUID) -> MealOut:
        meal = await self._owned_meal(user_id=user_id, meal_id=meal_id)
        return self._to_out(meal, await self._load_items(meal.id))

    async def delete(self, *, user_id: UUID, meal_id: UUID) -> None:
        meal = await self._owned_meal(user_id=user_id, meal_id=meal_id)
        await self.db.execute(delete(MealItem).where(MealItem.meal_id == meal.id))
        await self.db.delete(meal)
        await self.db.commit()

    async def log(
        self,
        *,
        user_id: UUID,
        meal_id: UUID,
        logged_at: date,
        meal_category: MealCategory,
    ) -> list[FoodDiaryEntryOut]:
        """Expand a saved meal into ordinary diary entries."""
        meal = await self._owned_meal(user_id=user_id, meal_id=meal_id)
        rows = await self._load_items(meal.id)

        created: list[FoodDiaryEntryOut] = []
        for item, food, nutrition in rows:
            entry = await self.diary.create_entry(
                user_id=user_id,
                food_id=item.food_id,
                logged_at=logged_at,
                meal_category=meal_category,
                quantity=float(item.quantity),
                unit=item.unit,
                source=LogSource.MANUAL,
            )
            created.append(_entry_to_out(entry, food, nutrition))
        await self.db.commit()
        return created

    async def _owned_meal(self, *, user_id: UUID, meal_id: UUID) -> Meal:
        result = await self.db.execute(
            select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id)
        )
        meal = result.scalar_one_or_none()
        if meal is None:
            # Deliberately indistinguishable from "does not exist": telling a
            # caller that a meal exists but belongs to someone else leaks the
            # existence of another user's data.
            raise MealNotFoundError
        return meal


__all__ = ["MealFoodNotAccessibleError", "MealNotFoundError", "MealService"]
