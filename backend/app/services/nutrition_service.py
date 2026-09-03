"""Deterministic nutrition scaling — no AI involved.

The nutrition database (custom foods, eventually an external provider) is
the source of truth for nutrition values; this module only does the
grams-based arithmetic to scale a food's per-serving/per-100g values to
however much of it was actually logged.
"""

from dataclasses import dataclass

from app.models.nutrition import LogUnit


class MissingServingSizeError(Exception):
    """Raised when logging by servings but the food has no serving_grams."""


@dataclass(frozen=True)
class NutritionValues:
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None


def grams_for_quantity(*, quantity: float, unit: LogUnit, serving_grams: float | None) -> float:
    if unit == LogUnit.GRAM:
        return quantity
    if serving_grams is None:
        raise MissingServingSizeError
    return quantity * serving_grams


def scale_nutrition(
    *,
    per_grams: float,
    calories_kcal: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    fiber_g: float | None,
    grams: float,
) -> NutritionValues:
    factor = grams / per_grams
    return NutritionValues(
        calories_kcal=round(calories_kcal * factor, 1),
        protein_g=round(protein_g * factor, 1),
        carbs_g=round(carbs_g * factor, 1),
        fat_g=round(fat_g * factor, 1),
        fiber_g=round(fiber_g * factor, 1) if fiber_g is not None else None,
    )
