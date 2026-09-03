from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.calorie_service import GoalIntensity, GoalType


class GoalCreateRequest(BaseModel):
    goal_type: GoalType
    intensity: GoalIntensity = GoalIntensity.STANDARD
    current_weight_kg: float = Field(gt=0, le=500)
    target_weight_kg: float | None = Field(default=None, gt=0, le=500)
    # Required to be explicitly true when the computed target is flagged
    # unsafe — the app never silently creates an aggressive/unsafe goal.
    acknowledge_risk: bool = False


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    goal_type: GoalType
    intensity: GoalIntensity
    target_weight_kg: float | None
    target_calories: int
    target_protein_g: int
    target_carbs_g: int
    target_fat_g: int
    target_water_ml: int
    is_active: bool
    created_at: datetime


class CalorieCalculationWarning(BaseModel):
    is_safe: bool
    warnings: list[str]
    safer_alternative_calories: int | None
