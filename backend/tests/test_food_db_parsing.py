"""Pure validation rules for provider payloads -- no transport, no database.

Kept out of `test_barcode.py` because these are synchronous and that module
applies an asyncio mark to everything in it.
"""

import pytest

from app.services.food_db.client import parse_openfoodfacts_product
from app.services.food_db.exceptions import UnusableProductDataError

BARCODE = "5000112637922"


def _nutriments(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "energy-kcal_100g": 350,
        "proteins_100g": 20,
        "carbohydrates_100g": 40,
        "fat_100g": 10,
        "fiber_100g": 3,
    }
    base.update(overrides)
    return base


def test_parse_accepts_a_well_formed_product() -> None:
    product = parse_openfoodfacts_product(
        BARCODE,
        {
            "product_name": "Protein Bar",
            "brands": "TestBrand",
            "serving_size": "1 bar (60 g)",
            "serving_quantity": 60,
            "nutriments": _nutriments(),
        },
    )

    assert product.name == "Protein Bar"
    assert product.per_grams == 100.0
    assert product.serving_grams == 60.0
    assert product.calories_kcal == 350.0
    assert product.fiber_g == 3.0


def test_parse_accepts_numbers_sent_as_strings() -> None:
    """Open Food Facts returns numeric fields as strings for some products."""
    product = parse_openfoodfacts_product(
        BARCODE,
        {
            "product_name": "Stringy Product",
            "serving_quantity": "60",
            "nutriments": _nutriments(**{"energy-kcal_100g": "350.5"}),
        },
    )

    assert product.calories_kcal == 350.5
    assert product.serving_grams == 60.0


def test_parse_falls_back_to_a_100g_serving_when_none_is_given() -> None:
    """Without a serving size the food could be created but never logged by
    the serving unit, so it falls back to the basis the data already uses."""
    product = parse_openfoodfacts_product(
        BARCODE,
        {"product_name": "No Serving Info", "nutriments": _nutriments()},
    )

    assert product.serving_grams == 100.0
    assert product.serving_description == "100 g"


@pytest.mark.parametrize(
    ("description", "product"),
    [
        ("no name", {"nutriments": _nutriments()}),
        ("empty name", {"product_name": "   ", "nutriments": _nutriments()}),
        ("no nutriments", {"product_name": "X"}),
        (
            "missing calories",
            {"product_name": "X", "nutriments": _nutriments(**{"energy-kcal_100g": None})},
        ),
        (
            "missing protein",
            {"product_name": "X", "nutriments": _nutriments(proteins_100g="")},
        ),
        (
            "calories above what any food can contain",
            {"product_name": "X", "nutriments": _nutriments(**{"energy-kcal_100g": 3500})},
        ),
        (
            "negative macro",
            {"product_name": "X", "nutriments": _nutriments(fat_100g=-5)},
        ),
        (
            "macros summing past 100 g per 100 g",
            {
                "product_name": "X",
                "nutriments": _nutriments(
                    proteins_100g=50, carbohydrates_100g=50, fat_100g=50
                ),
            },
        ),
    ],
)
def test_parse_rejects_unusable_products(
    description: str, product: dict[str, object]
) -> None:
    with pytest.raises(UnusableProductDataError):
        parse_openfoodfacts_product(BARCODE, product)


def test_parse_drops_an_absurd_fibre_value_without_rejecting_the_product() -> None:
    """Fibre is optional, so a bad value is dropped rather than costing the
    user an otherwise-usable product."""
    product = parse_openfoodfacts_product(
        BARCODE,
        {"product_name": "X", "nutriments": _nutriments(fiber_100g=9999)},
    )

    assert product.fiber_g is None


def test_parse_truncates_overlong_provider_text_to_column_limits() -> None:
    product = parse_openfoodfacts_product(
        BARCODE,
        {
            "product_name": "N" * 500,
            "brands": "B" * 500,
            "nutriments": _nutriments(),
        },
    )

    assert len(product.name) == 200
    assert product.brand is not None
    assert len(product.brand) == 120


