"""Food search across the local database and, optionally, an external one.

The local `foods` table is always searched. The external provider is only
consulted when the caller asks for it *and* an operator has configured one:
unlike a barcode, a search term is something the user typed, and shipping
free-text off the server by default is not a decision this app makes for
them.

Imported products are cached as `external_db` foods, exactly like a barcode
scan, so a product only ever crosses the wire once and gets a stable id the
diary can reference.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition import Food, FoodNutrition
from app.repositories.nutrition_repository import FoodRepository
from app.services.food_db.client import FoodDbClient


class FoodSearchService:
    def __init__(self, db: AsyncSession, client: FoodDbClient | None = None) -> None:
        self.db = db
        self.client = client
        self.foods = FoodRepository(db)

    async def search(
        self,
        *,
        user_id: UUID,
        query: str,
        limit: int,
        offset: int,
        include_external: bool,
    ) -> list[tuple[Food, FoodNutrition]]:
        """Local matches first, then external ones to fill the page.

        Raises `FoodDbProviderError` if the external provider is asked and
        fails; the caller decides whether that is worth failing the request
        over or whether local results alone will do.
        """
        results = await self.foods.search(
            user_id=user_id, query=query, limit=limit, offset=offset
        )
        if not include_external or self.client is None:
            return results

        # The provider is not paged here. Asking it again for page two would
        # re-fetch the same head of its result list, so external results are
        # offered on the first page only rather than duplicated on every page.
        if offset > 0:
            return results

        remaining = limit - len(results)
        if remaining <= 0:
            return results

        products = await self.client.search_by_name(query, limit=remaining)
        known_ids = {food.id for food, _ in results}
        created = False
        for product in products:
            cached = await self.foods.find_by_barcode(product.barcode)
            if cached is None:
                cached = await self.foods.create_external_food(
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
                created = True
            if cached[0].id in known_ids:
                continue
            known_ids.add(cached[0].id)
            results.append(cached)

        if created:
            await self.db.commit()
        return results


__all__ = ["FoodSearchService"]
