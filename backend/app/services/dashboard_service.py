from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.activity_repository import ActivityRepository
from app.repositories.profile_repository import GoalRepository, ProfileRepository
from app.repositories.water_repository import WaterRepository
from app.repositories.weight_repository import WeightRepository
from app.repositories.workout_repository import WorkoutRepository, WorkoutSessionRepository
from app.schemas.dashboard import (
    ActivityProgress,
    CalorieProgress,
    DashboardOut,
    MacroProgress,
    WaterProgress,
    WorkoutSummary,
)
from app.services.food_diary_service import FoodDiaryService


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.profiles = ProfileRepository(db)
        self.goals = GoalRepository(db)
        self.weights = WeightRepository(db)
        self.water = WaterRepository(db)
        self.food_diary = FoodDiaryService(db)
        self.activity = ActivityRepository(db)
        self.workouts = WorkoutRepository(db)
        self.workout_sessions = WorkoutSessionRepository(db)

    async def get_dashboard(self, user_id: UUID, for_date: date) -> DashboardOut:
        profile = await self.profiles.get(user_id)
        goal = await self.goals.get_active(user_id)
        entries = await self.food_diary.list_for_day(user_id, for_date)
        latest_weight = await self.weights.get_latest_as_of(user_id, for_date)
        water_entries = await self.water.list_for_day(user_id, for_date)
        activity_entries = await self.activity.list_for_day(user_id, for_date)
        todays_workouts = await self._todays_workouts(user_id, for_date)

        consumed_calories = sum(e.calories_kcal for e in entries)
        consumed_protein = sum(e.protein_g for e in entries)
        consumed_carbs = sum(e.carbs_g for e in entries)
        consumed_fat = sum(e.fat_g for e in entries)
        consumed_water_ml = sum(w.amount_ml for w in water_entries)

        # Steps and burned calories stay None unless something actually
        # reported them: summing to 0 would assert the user didn't move, which
        # is a different claim from "nothing told us".
        reported_steps = [e.steps for e in activity_entries if e.steps is not None]
        reported_burn = [
            e.calories_burned for e in activity_entries if e.calories_burned is not None
        ]

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
            activity=ActivityProgress(
                entry_count=len(activity_entries),
                duration_min=sum(e.duration_min for e in activity_entries),
                steps=sum(reported_steps) if reported_steps else None,
                calories_burned=sum(reported_burn) if reported_burn else None,
            ),
            todays_workouts=todays_workouts,
            latest_weight_kg=float(latest_weight.weight_kg) if latest_weight else None,
            latest_weight_logged_at=latest_weight.logged_at if latest_weight else None,
        )

    async def _todays_workouts(self, user_id: UUID, for_date: date) -> list[WorkoutSummary]:
        """Sessions started on `for_date`, with the volume actually lifted.

        Sessions are listed newest-first and filtered in Python rather than by
        a date-range query: a user has a handful of sessions a day at most, and
        the repository's existing paging keeps the scan bounded.
        """
        sessions = await self.workout_sessions.list_for_user(user_id, limit=50, offset=0)
        summaries: list[WorkoutSummary] = []
        for session in sessions:
            if session.started_at.date() != for_date:
                continue
            sets = await self.workout_sessions.get_sets(session.id)
            volume = sum(
                float(s.weight_kg) * s.reps
                for s, _ in sets
                if s.weight_kg is not None and s.reps is not None
            )
            name: str | None = None
            if session.workout_id is not None:
                workout = await self.workouts.get_by_id(session.workout_id)
                name = workout.name if workout else None
            summaries.append(
                WorkoutSummary(
                    session_id=session.id,
                    workout_name=name,
                    started_at=session.started_at,
                    ended_at=session.ended_at,
                    set_count=len(sets),
                    total_volume_kg=round(volume, 1),
                )
            )
        return summaries
