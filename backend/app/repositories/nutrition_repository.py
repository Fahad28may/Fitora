from datetime import date
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition import Food, FoodDiaryEntry, FoodNutrition, FoodSource


class FoodRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_custom_food(
        self,
        *,
        owner_user_id: UUID,
        name: str,
        brand: str | None,
        serving_description: str,
        serving_grams: float,
        calories_kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        fiber_g: float | None,
    ) -> Food:
        food = Food(
            source=FoodSource.USER,
            owner_user_id=owner_user_id,
            name=name,
            brand=brand,
            serving_description=serving_description,
            serving_grams=serving_grams,
        )
        self.db.add(food)
        await self.db.flush()

        nutrition = FoodNutrition(
            food_id=food.id,
            per_grams=serving_grams,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            fiber_g=fiber_g,
        )
        self.db.add(nutrition)
        await self.db.flush()
        return food

    async def search(
        self, *, user_id: UUID, query: str, limit: int, offset: int
    ) -> list[tuple[Food, FoodNutrition]]:
        stmt = (
            select(Food, FoodNutrition)
            .join(FoodNutrition, FoodNutrition.food_id == Food.id)
            .where(
                Food.name.ilike(f"%{query}%"),
                or_(
                    Food.source == FoodSource.SYSTEM,
                    and_(Food.source == FoodSource.USER, Food.owner_user_id == user_id),
                ),
            )
            .order_by(Food.name)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_with_nutrition(
        self, food_id: UUID
    ) -> tuple[Food, FoodNutrition] | None:
        stmt = (
            select(Food, FoodNutrition)
            .join(FoodNutrition, FoodNutrition.food_id == Food.id)
            .where(Food.id == food_id)
        )
        result = await self.db.execute(stmt)
        row = result.first()
        return (row[0], row[1]) if row else None

    async def find_by_barcode(self, barcode: str) -> tuple[Food, FoodNutrition] | None:
        """Local cache lookup for a barcode, so a repeat scan of the same
        product does not hit the external provider again.

        Only shared (system / external-db) rows are considered: a user-created
        food is private to its owner, so matching one here would leak its
        existence to whoever else scans that barcode. Ordered by creation so a
        duplicate row -- possible if two scans of an uncached barcode race --
        still resolves to the same product every time.
        """
        stmt = (
            select(Food, FoodNutrition)
            .join(FoodNutrition, FoodNutrition.food_id == Food.id)
            .where(
                Food.barcode == barcode,
                Food.source.in_([FoodSource.SYSTEM, FoodSource.EXTERNAL_DB]),
            )
            .order_by(Food.created_at)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.first()
        return (row[0], row[1]) if row else None

    async def create_external_food(
        self,
        *,
        barcode: str,
        name: str,
        brand: str | None,
        serving_description: str,
        serving_grams: float,
        per_grams: float,
        calories_kcal: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        fiber_g: float | None,
    ) -> tuple[Food, FoodNutrition]:
        """Persist a product fetched from an external database. No
        `owner_user_id`: the row is public product data, not user data, so it
        must not be caught up in a user's cascade delete."""
        food = Food(
            source=FoodSource.EXTERNAL_DB,
            owner_user_id=None,
            name=name,
            brand=brand,
            barcode=barcode,
            serving_description=serving_description,
            serving_grams=serving_grams,
        )
        self.db.add(food)
        await self.db.flush()

        nutrition = FoodNutrition(
            food_id=food.id,
            per_grams=per_grams,
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            fiber_g=fiber_g,
        )
        self.db.add(nutrition)
        await self.db.flush()
        return food, nutrition

    async def is_readable_by(self, food: Food, user_id: UUID) -> bool:
        # System and external-database foods are shared reference data (public
        # product facts, no owner); user foods are private to their owner.
        #
        # Note this makes an external food readable by id to any authenticated
        # user, which is intended -- but `search` deliberately does not return
        # them, so one user cannot enumerate what another has scanned.
        if food.source in (FoodSource.SYSTEM, FoodSource.EXTERNAL_DB):
            return True
        return food.owner_user_id == user_id


class FoodDiaryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_entry(self, **fields: object) -> FoodDiaryEntry:
        entry = FoodDiaryEntry(**fields)
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def list_for_day(
        self, user_id: UUID, logged_at: date
    ) -> list[tuple[FoodDiaryEntry, Food, FoodNutrition]]:
        stmt = (
            select(FoodDiaryEntry, Food, FoodNutrition)
            .join(Food, Food.id == FoodDiaryEntry.food_id)
            .join(FoodNutrition, FoodNutrition.food_id == Food.id)
            .where(FoodDiaryEntry.user_id == user_id, FoodDiaryEntry.logged_at == logged_at)
            .order_by(FoodDiaryEntry.created_at)
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def get_by_id(self, entry_id: UUID) -> FoodDiaryEntry | None:
        result = await self.db.execute(
            select(FoodDiaryEntry).where(FoodDiaryEntry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, entry: FoodDiaryEntry) -> None:
        await self.db.delete(entry)
        await self.db.flush()
