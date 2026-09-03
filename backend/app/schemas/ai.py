from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.nutrition import FoodOut


class ParsedFoodItem(BaseModel):
    """Raw shape requested from the model — validated before use for
    anything else. See docs/ai-safety.md 'Output validation pipeline'."""

    name: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, le=1000)
    unit: str = Field(min_length=1, max_length=30)


class FoodParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class ParsedFoodItemOut(BaseModel):
    name: str
    quantity: float
    unit: str
    matches: list[FoodOut]


class FoodParseResponse(BaseModel):
    items: list[ParsedFoodItemOut]


class CoachMessageCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class CoachMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
