from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import age_years
from app.models.goal import Goal
from app.models.profile import UserProfile
from app.repositories.profile_repository import GoalRepository, ProfileRepository
from app.services.calorie_service import CalorieTargetResult, calculate_targets


class IncompleteProfileError(Exception):
    """Raised when the profile lacks the fields required to compute targets."""


class UnsafeGoalNotAcknowledgedError(Exception):
    def __init__(self, result: CalorieTargetResult) -> None:
        self.result = result
        super().__init__("Goal target requires explicit risk acknowledgement")


def _require_complete_profile(profile: UserProfile | None) -> UserProfile:
    if (
        profile is None
        or profile.sex is None
        or profile.height_cm is None
        or profile.date_of_birth is None
        or profile.activity_level is None
    ):
        raise IncompleteProfileError
    return profile


class GoalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.profiles = ProfileRepository(db)
        self.goals = GoalRepository(db)

    async def create_goal(
        self,
        *,
        user_id: UUID,
        goal_type: str,
        intensity: str,
        current_weight_kg: float,
        target_weight_kg: float | None,
        acknowledge_risk: bool,
    ) -> Goal:
        profile = _require_complete_profile(await self.profiles.get(user_id))

        result = calculate_targets(
            sex=profile.sex,  # type: ignore[arg-type]
            weight_kg=current_weight_kg,
            height_cm=float(profile.height_cm),  # type: ignore[arg-type]
            age_years=age_years(profile.date_of_birth),  # type: ignore[arg-type]
            activity_level=profile.activity_level,  # type: ignore[arg-type]
            goal_type=goal_type,  # type: ignore[arg-type]
            intensity=intensity,  # type: ignore[arg-type]
        )

        if not result.is_safe and not acknowledge_risk:
            raise UnsafeGoalNotAcknowledgedError(result)

        await self.goals.deactivate_all(user_id)
        goal = await self.goals.create(
            user_id=user_id,
            goal_type=goal_type,
            intensity=intensity,
            target_weight_kg=target_weight_kg,
            target_calories=result.target_calories,
            target_protein_g=result.macros.protein_g,
            target_carbs_g=result.macros.carbs_g,
            target_fat_g=result.macros.fat_g,
        )
        await self.db.commit()
        return goal

    async def get_active_goal(self, user_id: UUID) -> Goal | None:
        return await self.goals.get_active(user_id)
