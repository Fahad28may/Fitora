from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.profile_repository import GoalRepository, ProfileRepository
from app.repositories.water_repository import WaterRepository
from app.repositories.weight_repository import WeightRepository
from app.schemas.dashboard import CalorieProgress, DashboardOut, MacroProgress, WaterProgress
from app.services.food_diary_service import FoodDiaryService


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.profiles = ProfileRepository(db)
        self.goals = GoalRepository(db)
        self.weights = WeightRepository(db)
        self.water = WaterRepository(db)
        self.food_diary = FoodDiaryService(db)

    async def get_dashboard(self, user_id: UUID, for_date: date) -> DashboardOut:
        profile = await self.profiles.get(user_id)
        goal = await self.goals.get_active(user_id)
        entries = await self.food_diary.list_for_day(user_id, for_date)
        latest_weight = await self.weights.get_latest_as_of(user_id, for_date)
        water_entries = await self.water.list_for_day(user_id, for_date)

        consumed_calories = sum(e.calories_kcal for e in entries)
        consumed_protein = sum(e.protein_g for e in entries)
        consumed_carbs = sum(e.carbs_g for e in entries)
        consumed_fat = sum(e.fat_g for e in entries)
        consumed_water_ml = sum(w.amount_ml for w in water_entries)

        target_calories = goal.target_calories if goal else None
        remaining = (target_calories - consumed_calories) if target_calories is not None else None

        return DashboardOut(
            date=for_date,
            has_profile=profile is not None,
            has_active_goal=goal is not None,
            calories=CalorieProgress(
                target=target_calories, consumed=consumed_calories, remaining=remaining
            ),
            protein=MacroProgress(
                target_g=goal.target_protein_g if goal else None, consumed_g=consumed_protein
            ),
            carbs=MacroProgress(
                target_g=goal.target_carbs_g if goal else None, consumed_g=consumed_carbs
            ),
            fat=MacroProgress(
                target_g=goal.target_fat_g if goal else None, consumed_g=consumed_fat
            ),
            water=WaterProgress(
                target_ml=goal.target_water_ml if goal else None, consumed_ml=consumed_water_ml
            ),
            latest_weight_kg=float(latest_weight.weight_kg) if latest_weight else None,
            latest_weight_logged_at=latest_weight.logged_at if latest_weight else None,
        )
