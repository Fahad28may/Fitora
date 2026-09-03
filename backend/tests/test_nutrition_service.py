import pytest

from app.models.nutrition import LogUnit
from app.services.nutrition_service import (
    MissingServingSizeError,
    grams_for_quantity,
    scale_nutrition,
)


def test_grams_for_quantity_gram_unit_is_direct() -> None:
    assert grams_for_quantity(quantity=150, unit=LogUnit.GRAM, serving_grams=None) == 150


def test_grams_for_quantity_serving_unit_multiplies_by_serving_grams() -> None:
    assert grams_for_quantity(quantity=2, unit=LogUnit.SERVING, serving_grams=50) == 100


def test_grams_for_quantity_serving_unit_without_serving_grams_raises() -> None:
    with pytest.raises(MissingServingSizeError):
        grams_for_quantity(quantity=2, unit=LogUnit.SERVING, serving_grams=None)


def test_scale_nutrition_at_same_grams_is_unchanged() -> None:
    result = scale_nutrition(
        per_grams=100,
        calories_kcal=200,
        protein_g=10,
        carbs_g=20,
        fat_g=5,
        fiber_g=3,
        grams=100,
    )
    assert result.calories_kcal == 200
    assert result.protein_g == 10
    assert result.fiber_g == 3


def test_scale_nutrition_doubles_at_double_grams() -> None:
    result = scale_nutrition(
        per_grams=100,
        calories_kcal=200,
        protein_g=10,
        carbs_g=20,
        fat_g=5,
        fiber_g=3,
        grams=200,
    )
    assert result.calories_kcal == 400
    assert result.protein_g == 20
    assert result.fiber_g == 6


def test_scale_nutrition_handles_missing_fiber() -> None:
    result = scale_nutrition(
        per_grams=100,
        calories_kcal=200,
        protein_g=10,
        carbs_g=20,
        fat_g=5,
        fiber_g=None,
        grams=150,
    )
    assert result.fiber_g is None
    assert result.calories_kcal == 300
