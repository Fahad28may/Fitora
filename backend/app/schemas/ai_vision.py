from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.nutrition import FoodOut

Confidence = Literal["high", "medium", "low"]

MAX_ITEMS = 12
MAX_INGREDIENTS = 15

# A calorie range narrower than this fraction of its own midpoint is claiming
# precision a photograph cannot support (§7: never say "exactly 647 calories").
# Enforced by widening in the service, not just asked for in the prompt.
MIN_RANGE_FRACTION = 0.20


class RecognizedFoodItem(BaseModel):
    """One food the vision model believes it sees.

    Calories are always a range. There is no single-number field on purpose:
    if the schema cannot express "exactly 647 kcal", no amount of model
    drift can start reporting it.
    """

    name: str = Field(min_length=1, max_length=120)
    # Generous on purpose: with unit="gram" a real portion is routinely in
    # the hundreds, so a tight cap here silently rejects every gram-based
    # answer the model gives. (Found live — a 400 g jar failed validation and
    # surfaced to the user as "couldn't read that photo".) The user corrects
    # the number before anything is logged, so a loose upper bound costs
    # nothing; the diary's own validation is what actually guards the data.
    estimated_quantity: float = Field(gt=0, le=5000)
    unit: Literal[
        "piece", "slice", "cup", "bowl", "glass", "tablespoon", "serving", "gram"
    ]
    portion_note: str = Field(default="", max_length=160)
    calories_min: int = Field(ge=0, le=5000)
    calories_max: int = Field(ge=0, le=5000)
    confidence: Confidence
    ingredients: list[str] = Field(default_factory=list, max_length=MAX_INGREDIENTS)

    @model_validator(mode="after")
    def _range_is_ordered(self) -> "RecognizedFoodItem":
        if self.calories_max < self.calories_min:
            raise ValueError("calories_max must not be below calories_min")
        return self


class RecognizedFoodItemOut(RecognizedFoodItem):
    """A recognized item plus candidate matches from the food database.

    The user picks a match and confirms it; that confirmed food is what gets
    logged. The model's own calorie estimate is never written to the diary —
    it is shown so the user can sanity-check their choice.
    """

    matches: list[FoodOut] = Field(default_factory=list)


class PhotoRecognitionOut(BaseModel):
    items: list[RecognizedFoodItemOut]
    overall_note: str = Field(default="", max_length=300)
    #: Always true. Stated in the payload so a client can't render this as
    #: settled fact without having been told otherwise.
    is_estimate: bool = True
    #: Always false today — the image is processed in memory and dropped.
    image_retained: bool = False
