from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_entry import ActivityEntry, ActivitySource, ActivityType


class ActivityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID,
        logged_at: date,
        activity_type: ActivityType,
        duration_min: int,
        distance_km: float | None,
        steps: int | None,
        calories_burned: int | None,
        source: ActivitySource,
        notes: str | None,
    ) -> ActivityEntry:
        entry = ActivityEntry(
            user_id=user_id,
            logged_at=logged_at,
            activity_type=activity_type,
            duration_min=duration_min,
            distance_km=distance_km,
            steps=steps,
            calories_burned=calories_burned,
            source=source,
            notes=notes,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def list_for_day(self, user_id: UUID, logged_at: date) -> list[ActivityEntry]:
        result = await self.db.execute(
            select(ActivityEntry)
            .where(ActivityEntry.user_id == user_id, ActivityEntry.logged_at == logged_at)
            .order_by(ActivityEntry.created_at)
        )
        return list(result.scalars().all())

    async def get_by_id(self, entry_id: UUID) -> ActivityEntry | None:
        result = await self.db.execute(
            select(ActivityEntry).where(ActivityEntry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, entry: ActivityEntry) -> None:
        await self.db.delete(entry)
        await self.db.flush()
