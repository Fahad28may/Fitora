from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exercise import Exercise


class ExerciseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self, *, query: str | None, muscle_group: str | None, limit: int, offset: int
    ) -> list[Exercise]:
        stmt = select(Exercise)
        if query:
            stmt = stmt.where(Exercise.name.ilike(f"%{query}%"))
        stmt = stmt.order_by(Exercise.name)

        if muscle_group is None:
            # No further filtering needed, so paginate at the database.
            stmt = stmt.limit(limit).offset(offset)
            result = await self.db.execute(stmt)
            return list(result.scalars().all())

        # muscle_groups is stored as a JSON array — there's no portable JSON
        # containment operator across SQLite (tests) and Postgres, and the
        # exercise library is small, so filter and paginate in Python instead
        # of pushing an inconsistent partial filter down to the database.
        result = await self.db.execute(stmt)
        matching = [e for e in result.scalars().all() if muscle_group in e.muscle_groups]
        return matching[offset : offset + limit]

    async def get_by_id(self, exercise_id: UUID) -> Exercise | None:
        result = await self.db.execute(select(Exercise).where(Exercise.id == exercise_id))
        return result.scalar_one_or_none()
