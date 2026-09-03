from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.water_entry import WaterEntry


class WaterRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: UUID, logged_at: date, amount_ml: int) -> WaterEntry:
        entry = WaterEntry(user_id=user_id, logged_at=logged_at, amount_ml=amount_ml)
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def list_for_day(self, user_id: UUID, logged_at: date) -> list[WaterEntry]:
        result = await self.db.execute(
            select(WaterEntry)
            .where(WaterEntry.user_id == user_id, WaterEntry.logged_at == logged_at)
            .order_by(WaterEntry.created_at)
        )
        return list(result.scalars().all())

    async def get_by_id(self, entry_id: UUID) -> WaterEntry | None:
        result = await self.db.execute(select(WaterEntry).where(WaterEntry.id == entry_id))
        return result.scalar_one_or_none()

    async def delete(self, entry: WaterEntry) -> None:
        await self.db.delete(entry)
        await self.db.flush()
