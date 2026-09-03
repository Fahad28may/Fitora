from datetime import date as date_type

from pydantic import BaseModel


class MacroProgress(BaseModel):
    target_g: int | None
    consumed_g: float


class CalorieProgress(BaseModel):
    target: int | None
    consumed: float
    remaining: float | None


class DashboardOut(BaseModel):
    date: date_type
    has_profile: bool
    has_active_goal: bool
    calories: CalorieProgress
    protein: MacroProgress
    carbs: MacroProgress
    fat: MacroProgress
    latest_weight_kg: float | None
    latest_weight_logged_at: date_type | None
