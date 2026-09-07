from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.nutrition import LogUnit, MealCategory

MAX_ITEMS_PER_MEAL = 50


class MealItemCreateRequest(BaseModel):
    food_id: UUID
    quantity: float = Field(gt=0, le=1000)
    unit: LogUnit = LogUnit.SERVING


class MealCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    items: list[MealItemCreateRequest] = Field(min_length=1, max_length=MAX_ITEMS_PER_MEAL)


class MealItemOut(BaseModel):
    id: UUID
    food_id: UUID
    food_name: str
    quantity: float
    unit: LogUnit
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class MealOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    items: list[MealItemOut]
    #: Computed on read from current food nutrition, like diary entries — not
    #: snapshotted when the meal was saved.
    total_calories_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float


class MealLogRequest(BaseModel):
    logged_at: date
    meal_category: MealCategory
