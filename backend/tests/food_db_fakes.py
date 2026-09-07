from app.services.food_db.client import ExternalProduct
from app.services.food_db.exceptions import FoodDbError


class FakeFoodDbClient:
    """Deterministic stand-in for the food database — the real provider isn't
    called in tests. Records every barcode it was asked for, so tests can
    assert that a cached lookup made no outbound request."""

    def __init__(self, products: dict[str, ExternalProduct]) -> None:
        self._products = products
        self.calls: list[str] = []

    async def fetch_by_barcode(self, barcode: str) -> ExternalProduct:
        self.calls.append(barcode)
        product = self._products.get(barcode)
        if product is None:
            from app.services.food_db.exceptions import ProductNotFoundError

            raise ProductNotFoundError(barcode)
        return product


class RaisingFoodDbClient:
    """Always fails with the given exception — for provider-outage and
    bad-data paths."""

    def __init__(self, error: FoodDbError) -> None:
        self._error = error
        self.calls: list[str] = []

    async def fetch_by_barcode(self, barcode: str) -> ExternalProduct:
        self.calls.append(barcode)
        raise self._error


def sample_product(
    barcode: str = "5000112637922",
    *,
    name: str = "Test Protein Bar",
    brand: str | None = "TestBrand",
    serving_grams: float = 60.0,
    calories_kcal: float = 350.0,
) -> ExternalProduct:
    return ExternalProduct(
        barcode=barcode,
        name=name,
        brand=brand,
        serving_description="1 bar (60 g)",
        serving_grams=serving_grams,
        per_grams=100.0,
        calories_kcal=calories_kcal,
        protein_g=20.0,
        carbs_g=40.0,
        fat_g=10.0,
        fiber_g=3.0,
    )
