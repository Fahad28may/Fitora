from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progress_photo import ProgressPhoto


class ProgressPhotoRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID,
        taken_at: date,
        storage_key: str,
        content_type: str,
        size_bytes: int,
    ) -> ProgressPhoto:
        photo = ProgressPhoto(
            user_id=user_id,
            taken_at=taken_at,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size_bytes,
        )
        self.db.add(photo)
        await self.db.flush()
        return photo

    async def list_for_user(self, user_id: UUID) -> list[ProgressPhoto]:
        result = await self.db.execute(
            select(ProgressPhoto)
            .where(ProgressPhoto.user_id == user_id)
            .order_by(ProgressPhoto.taken_at.desc(), ProgressPhoto.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, photo_id: UUID) -> ProgressPhoto | None:
        result = await self.db.execute(
            select(ProgressPhoto).where(ProgressPhoto.id == photo_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, photo: ProgressPhoto) -> None:
        await self.db.delete(photo)
        await self.db.flush()
