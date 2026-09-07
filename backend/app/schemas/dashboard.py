from datetime import date as date_type
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MacroProgress(BaseModel):
    target_g: int | None
    consumed_g: float


class CalorieProgress(BaseModel):
    target: int | None
    consumed: float
    remaining: float | None


class WaterProgress(BaseModel):
    target_ml: int | None
    consumed_ml: int


class ActivityProgress(BaseModel):
    """Today's movement. `steps` is None rather than 0 when nothing reported
    steps, so the UI can distinguish "no step data" from "you took no steps" —
    §16 asks for no fake precision, and a hard 0 would be a claim we can't
    make until a device integration exists."""

    entry_count: int
    duration_min: int
    steps: int | None
    calories_burned: int | None


class WorkoutSummary(BaseModel):
    session_id: UUID
    workout_name: str | None
    started_at: datetime
    ended_at: datetime | None
    set_count: int
    total_volume_kg: float


class DashboardOut(BaseModel):
    date: date_type
    has_profile: bool
    has_active_goal: bool
    calories: CalorieProgress
    protein: MacroProgress
    carbs: MacroProgress
    fat: MacroProgress
    water: WaterProgress
    activity: ActivityProgress
    todays_workouts: list[WorkoutSummary]
    latest_weight_kg: float | None
    latest_weight_logged_at: date_type | None
