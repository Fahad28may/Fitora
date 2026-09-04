from datetime import date as date_type
from enum import StrEnum

from pydantic import BaseModel


class RecommendationCategory(StrEnum):
    NUTRITION = "nutrition"
    HYDRATION = "hydration"
    ACTIVITY = "activity"
    WEIGHT = "weight"
    CONSISTENCY = "consistency"


class RecommendationPriority(StrEnum):
    # Ordered least-to-most urgent; the service sorts output by this.
    INFO = "info"
    SUGGESTION = "suggestion"
    WARNING = "warning"


class Recommendation(BaseModel):
    category: RecommendationCategory
    priority: RecommendationPriority
    title: str
    detail: str


class RecommendationsOut(BaseModel):
    generated_for: date_type
    window_days: int
    days_with_food_logged: int
    has_active_goal: bool
    recommendations: list[Recommendation]
