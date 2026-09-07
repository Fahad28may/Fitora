from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition import Food, FoodNutrition
from app.repositories.nutrition_repository import FoodRepository
from app.services.food_db.client import FoodDbClient


class BarcodeLookupService:
    """Resolves a barcode to a food row, cache-first.

    The local `foods` table doubles as the cache: the first scan of a product
    fetches it from the external provider and persists it as an
    `external_db` food, and every later scan of that barcode -- by any user --
    is answered from the database with no outbound request. That keeps repeat
    scans fast, keeps the provider's servers out of the hot path, and means a
    previously-scanned product still resolves if the provider is down.
    """

    def __init__(self, db: AsyncSession, client: FoodDbClient) -> None:
        self.db = db
        self.client = client
        self.foods = FoodRepository(db)

    async def lookup(self, barcode: str) -> tuple[Food, FoodNutrition]:
        """Returns the food for `barcode`, fetching and caching it if needed.

        Raises `ProductNotFoundError`, `UnusableProductDataError`, or
        `FoodDbProviderError` from `app.services.food_db.exceptions`.
        """
        cached = await self.foods.find_by_barcode(barcode)
        if cached is not None:
            return cached

        product = await self.client.fetch_by_barcode(barcode)
        food, nutrition = await self.foods.create_external_food(
            barcode=product.barcode,
            name=product.name,
            brand=product.brand,
            serving_description=product.serving_description,
            serving_grams=product.serving_grams,
            per_grams=product.per_grams,
            calories_kcal=product.calories_kcal,
            protein_g=product.protein_g,
            carbs_g=product.carbs_g,
            fat_g=product.fat_g,
            fiber_g=product.fiber_g,
        )
        await self.db.commit()
        return food, nutrition


__all__ = ["BarcodeLookupService"]
