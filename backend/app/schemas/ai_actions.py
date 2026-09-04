from datetime import date
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.nutrition import LogUnit, MealCategory
from app.schemas.nutrition import FoodOut


class AIActionType(StrEnum):
    LOG_WEIGHT = "log_weight"
    LOG_WATER = "log_water"
    LOG_FOOD = "log_food"
    NONE = "none"


# --- Raw parameter shapes requested from the model (untrusted → validated) ---
# These mirror the business-rule bounds of the equivalent manual endpoints, so
# a value the model invents can never exceed what a user could enter by hand.


class LogWeightParams(BaseModel):
    weight_kg: float = Field(gt=0, le=500)
    logged_at: date | None = None


class LogWaterParams(BaseModel):
    amount_ml: int = Field(gt=0, le=5000)
    logged_at: date | None = None


class LogFoodParams(BaseModel):
    food_query: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, le=1000)
    unit: LogUnit = LogUnit.SERVING
    meal_category: MealCategory
    logged_at: date | None = None


class RawProposal(BaseModel):
    """Top-level JSON shape the model must return. `parameters` is validated
    against the per-action model only after `action` is known."""

    action: AIActionType
    parameters: dict[str, object] = Field(default_factory=dict)
    summary: str = Field(default="", max_length=500)


# --- Propose (read-only): translate NL → a proposal the user must confirm ---


class ActionProposeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ProposedActionOut(BaseModel):
    action: AIActionType
    # Human-readable description the client shows for explicit confirmation.
    summary: str
    # False when the action is NONE or a food proposal matched no known food —
    # i.e. there's nothing safe to confirm-and-execute yet.
    executable: bool
    # Normalized echo of the validated parameters (never the raw model output).
    parameters: dict[str, object]
    # Only populated for log_food: candidate foods the user picks from.
    food_matches: list[FoodOut] = Field(default_factory=list)


# --- Confirm (write): deterministic, no AI. Discriminated on `action`. ---


class ConfirmLogWeight(BaseModel):
    action: Literal["log_weight"]
    weight_kg: float = Field(gt=0, le=500)
    logged_at: date | None = None


class ConfirmLogWater(BaseModel):
    action: Literal["log_water"]
    amount_ml: int = Field(gt=0, le=5000)
    logged_at: date | None = None


class ConfirmLogFood(BaseModel):
    action: Literal["log_food"]
    food_id: UUID
    quantity: float = Field(gt=0, le=1000)
    unit: LogUnit = LogUnit.SERVING
    meal_category: MealCategory
    logged_at: date | None = None


ConfirmActionRequest = Annotated[
    ConfirmLogWeight | ConfirmLogWater | ConfirmLogFood,
    Field(discriminator="action"),
]


class ActionResultOut(BaseModel):
    action: AIActionType
    status: Literal["executed"]
    summary: str
    resource_id: UUID
