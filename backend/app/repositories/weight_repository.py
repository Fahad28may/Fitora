from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weight_entry import WeightEntry


class WeightRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: UUID, logged_at: date, weight_kg: float) -> WeightEntry:
        entry = WeightEntry(user_id=user_id, logged_at=logged_at, weight_kg=weight_kg)
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        offset: int,
    ) -> list[WeightEntry]:
        query = select(WeightEntry).where(WeightEntry.user_id == user_id)
        if date_from is not None:
            query = query.where(WeightEntry.logged_at >= date_from)
        if date_to is not None:
            query = query.where(WeightEntry.logged_at <= date_to)
        query = (
            query.order_by(WeightEntry.logged_at.desc(), WeightEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest(self, user_id: UUID) -> WeightEntry | None:
        query = (
            select(WeightEntry)
            .where(WeightEntry.user_id == user_id)
            .order_by(WeightEntry.logged_at.desc(), WeightEntry.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, entry_id: UUID) -> WeightEntry | None:
        result = await self.db.execute(select(WeightEntry).where(WeightEntry.id == entry_id))
        return result.scalar_one_or_none()

    async def delete(self, entry: WeightEntry) -> None:
        await self.db.delete(entry)
        await self.db.flush()
