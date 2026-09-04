from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal
from app.models.weight_entry import WeightEntry
from app.repositories.profile_repository import GoalRepository
from app.repositories.water_repository import WaterRepository
from app.repositories.weight_repository import WeightRepository
from app.repositories.workout_repository import WorkoutSessionRepository
from app.schemas.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationsOut,
)
from app.services.calorie_service import GoalType
from app.services.food_diary_service import FoodDiaryService

# How many days back (inclusive of the reference day) each signal looks.
WINDOW_DAYS = 7

# A signal is only trustworthy once there's enough logged data behind it —
# below this many logged days we stay quiet rather than guess from noise.
MIN_LOGGED_DAYS_FOR_NUTRITION = 3

# Deterministic thresholds (fractions of the user's own targets). Kept
# conservative so a single heavy day doesn't trigger a warning.
CALORIE_OVER_FRACTION = 1.15
CALORIE_UNDER_FRACTION = 0.70
PROTEIN_UNDER_FRACTION = 0.80
WATER_UNDER_FRACTION = 0.70

_PRIORITY_ORDER = {
    RecommendationPriority.WARNING: 0,
    RecommendationPriority.SUGGESTION: 1,
    RecommendationPriority.INFO: 2,
}


class RecommendationService:
    """Deterministic, rule-based recommendations — no LLM involved.

    Every rule is guarded by data availability: a signal is only emitted when
    there's real logged data behind it. Language stays approximate (never
    false precision) and never encourages extreme restriction, consistent with
    the health guardrails in docs/ai-safety.md.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.goals = GoalRepository(db)
        self.weights = WeightRepository(db)
        self.water = WaterRepository(db)
        self.sessions = WorkoutSessionRepository(db)
        self.food_diary = FoodDiaryService(db)

    async def get_recommendations(self, user_id: UUID, for_date: date) -> RecommendationsOut:
        window_start = for_date - timedelta(days=WINDOW_DAYS - 1)
        goal = await self.goals.get_active(user_id)

        # Per-day food + water totals across the window.
        daily_calories: list[float] = []
        daily_protein: list[float] = []
        daily_water: list[int] = []
        days_with_food = 0
        for offset in range(WINDOW_DAYS):
            day = window_start + timedelta(days=offset)
            entries = await self.food_diary.list_for_day(user_id, day)
            if entries:
                days_with_food += 1
                daily_calories.append(sum(e.calories_kcal for e in entries))
                daily_protein.append(sum(e.protein_g for e in entries))
            water_entries = await self.water.list_for_day(user_id, day)
            if water_entries:
                daily_water.append(sum(w.amount_ml for w in water_entries))

        weight_entries = await self.weights.list_for_user(
            user_id, date_from=window_start, date_to=for_date, limit=100, offset=0
        )
        sessions = await self.sessions.list_for_user(user_id, limit=100, offset=0)
        sessions_in_window = [
            s for s in sessions if window_start <= s.started_at.date() <= for_date
        ]

        recs: list[Recommendation] = []

        if goal is None:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.CONSISTENCY,
                    priority=RecommendationPriority.SUGGESTION,
                    title="Set a goal to get tailored guidance",
                    detail=(
                        "You don't have an active goal yet. Setting one lets Fitora tailor "
                        "calorie, protein, and hydration targets to what you're working toward."
                    ),
                )
            )

        self._add_consistency_recs(recs, days_with_food)
        if goal is not None:
            self._add_nutrition_recs(recs, goal, daily_calories, daily_protein)
            self._add_hydration_recs(recs, goal, daily_water)
            self._add_weight_recs(recs, goal, weight_entries)
        self._add_activity_recs(recs, len(sessions_in_window))

        if not recs:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.CONSISTENCY,
                    priority=RecommendationPriority.INFO,
                    title="You're on track",
                    detail=(
                        "Your recent logging looks consistent and in line with your targets. "
                        "Keep it up."
                    ),
                )
            )

        recs.sort(key=lambda r: _PRIORITY_ORDER[r.priority])

        return RecommendationsOut(
            generated_for=for_date,
            window_days=WINDOW_DAYS,
            days_with_food_logged=days_with_food,
            has_active_goal=goal is not None,
            recommendations=recs,
        )

    def _add_consistency_recs(self, recs: list[Recommendation], days_with_food: int) -> None:
        if days_with_food == 0:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.CONSISTENCY,
                    priority=RecommendationPriority.SUGGESTION,
                    title="Start logging your meals",
                    detail=(
                        "You haven't logged any food in the last week. Even a few days of "
                        "logging gives Fitora enough to spot patterns and help."
                    ),
                )
            )
        elif days_with_food < WINDOW_DAYS // 2:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.CONSISTENCY,
                    priority=RecommendationPriority.SUGGESTION,
                    title="Log a little more consistently",
                    detail=(
                        f"You logged food on {days_with_food} of the last {WINDOW_DAYS} days. "
                        "More consistent logging makes trends and estimates more reliable."
                    ),
                )
            )

    def _add_nutrition_recs(
        self,
        recs: list[Recommendation],
        goal: Goal,
        daily_calories: list[float],
        daily_protein: list[float],
    ) -> None:
        if len(daily_calories) < MIN_LOGGED_DAYS_FOR_NUTRITION:
            return
        avg_calories = sum(daily_calories) / len(daily_calories)
        avg_protein = sum(daily_protein) / len(daily_protein)

        if avg_calories < goal.target_calories * CALORIE_UNDER_FRACTION:
            # Safety-first: flag persistent large under-eating rather than
            # treating it as "good progress", per the health guardrails.
            recs.append(
                Recommendation(
                    category=RecommendationCategory.NUTRITION,
                    priority=RecommendationPriority.WARNING,
                    title="You may be eating too little",
                    detail=(
                        "Your logged intake has been well below your calorie target on recent "
                        "days. Very low intake can backfire — consider eating closer to your "
                        "target, and speak to a qualified professional if this is intentional."
                    ),
                )
            )
        elif avg_calories > goal.target_calories * CALORIE_OVER_FRACTION:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.NUTRITION,
                    priority=RecommendationPriority.SUGGESTION,
                    title="Trending above your calorie target",
                    detail=(
                        "Your logged intake has been running above your daily calorie target. "
                        "If your goal depends on it, small adjustments to portion sizes can help."
                    ),
                )
            )

        if avg_protein < goal.target_protein_g * PROTEIN_UNDER_FRACTION:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.NUTRITION,
                    priority=RecommendationPriority.SUGGESTION,
                    title="Protein is running low",
                    detail=(
                        "Your protein intake has been below target lately. Adding a protein "
                        "source to a meal or two can help you get closer."
                    ),
                )
            )

    def _add_hydration_recs(
        self, recs: list[Recommendation], goal: Goal, daily_water: list[int]
    ) -> None:
        if not daily_water:
            return
        avg_water = sum(daily_water) / len(daily_water)
        if avg_water < goal.target_water_ml * WATER_UNDER_FRACTION:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.HYDRATION,
                    priority=RecommendationPriority.SUGGESTION,
                    title="Hydration is below your target",
                    detail=(
                        "On the days you logged water, you were under your daily target. "
                        "Keeping a bottle handy is an easy way to close the gap."
                    ),
                )
            )

    def _add_weight_recs(
        self, recs: list[Recommendation], goal: Goal, weight_entries: list[WeightEntry]
    ) -> None:
        if len(weight_entries) < 2:
            return
        # list_for_user returns newest-first.
        latest = float(weight_entries[0].weight_kg)
        earliest = float(weight_entries[-1].weight_kg)
        change = latest - earliest

        if goal.goal_type == GoalType.LOSE_WEIGHT and change > 0:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.WEIGHT,
                    priority=RecommendationPriority.INFO,
                    title="Weight is trending up",
                    detail=(
                        "Your recent weight is up compared to earlier in the week, while your "
                        "goal is to lose. Short-term swings are normal — worth watching the trend."
                    ),
                )
            )
        elif goal.goal_type == GoalType.GAIN_WEIGHT and change < 0:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.WEIGHT,
                    priority=RecommendationPriority.INFO,
                    title="Weight is trending down",
                    detail=(
                        "Your recent weight is down compared to earlier in the week, while your "
                        "goal is to gain. Short-term swings are normal — worth watching the trend."
                    ),
                )
            )

    def _add_activity_recs(self, recs: list[Recommendation], sessions_in_window: int) -> None:
        if sessions_in_window == 0:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.ACTIVITY,
                    priority=RecommendationPriority.SUGGESTION,
                    title="No workouts logged this week",
                    detail=(
                        "You haven't logged any workouts in the last week. Even a couple of "
                        "short sessions add up over time."
                    ),
                )
            )
        elif sessions_in_window >= 3:
            recs.append(
                Recommendation(
                    category=RecommendationCategory.ACTIVITY,
                    priority=RecommendationPriority.INFO,
                    title="Solid training week",
                    detail=(
                        f"You logged {sessions_in_window} workouts in the last week — nice "
                        "consistency."
                    ),
                )
            )
