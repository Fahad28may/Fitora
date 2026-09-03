from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.body_measurement import BodyMeasurement


class MeasurementRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: UUID, **fields: object) -> BodyMeasurement:
        measurement = BodyMeasurement(user_id=user_id, **fields)
        self.db.add(measurement)
        await self.db.flush()
        return measurement

    async def list_for_user(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> list[BodyMeasurement]:
        result = await self.db.execute(
            select(BodyMeasurement)
            .where(BodyMeasurement.user_id == user_id)
            .order_by(BodyMeasurement.logged_at.desc(), BodyMeasurement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id(self, measurement_id: UUID) -> BodyMeasurement | None:
        result = await self.db.execute(
            select(BodyMeasurement).where(BodyMeasurement.id == measurement_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, measurement: BodyMeasurement) -> None:
        await self.db.delete(measurement)
        await self.db.flush()
