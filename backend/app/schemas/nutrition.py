from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.nutrition import FoodSource, LogSource, LogUnit, MealCategory


class FoodCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=120)
    serving_description: str = Field(min_length=1, max_length=120)
    serving_grams: float = Field(gt=0, le=5000)
    calories_kcal: float = Field(ge=0, le=10000)
    protein_g: float = Field(ge=0, le=1000)
    carbs_g: float = Field(ge=0, le=1000)
    fat_g: float = Field(ge=0, le=1000)
    fiber_g: float | None = Field(default=None, ge=0, le=1000)


class FoodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: FoodSource
    name: str
    brand: str | None
    serving_description: str
    serving_grams: float | None
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None


class FoodDiaryEntryCreateRequest(BaseModel):
    food_id: UUID
    logged_at: date
    meal_category: MealCategory
    quantity: float = Field(gt=0, le=1000)
    unit: LogUnit = LogUnit.SERVING
    source: LogSource = LogSource.MANUAL


class FoodDiaryEntryOut(BaseModel):
    id: UUID
    food_id: UUID
    food_name: str
    logged_at: date
    meal_category: MealCategory
    quantity: float
    unit: LogUnit
    source: LogSource
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    created_at: datetime
