from datetime import date
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progress_photo import ProgressPhoto
from app.repositories.progress_photo_repository import ProgressPhotoRepository
from app.schemas.progress_photo import ProgressPhotoOut
from app.services.storage.base import ObjectStorage
from app.services.storage.image_validation import MAX_PHOTO_BYTES, sniff_image


class InvalidImageError(Exception):
    """Uploaded bytes aren't a supported image type."""


class PhotoTooLargeError(Exception):
    """Uploaded file exceeds the size ceiling."""


class PhotoNotFoundError(Exception):
    """No such photo owned by the requesting user."""


class ProgressPhotoService:
    def __init__(self, db: AsyncSession, storage: ObjectStorage) -> None:
        self.db = db
        self.storage = storage
        self.repo = ProgressPhotoRepository(db)

    async def _to_out(self, photo: ProgressPhoto) -> ProgressPhotoOut:
        url = await self.storage.presigned_get_url(key=photo.storage_key)
        return ProgressPhotoOut(
            id=photo.id,
            taken_at=photo.taken_at,
            content_type=photo.content_type,
            size_bytes=photo.size_bytes,
            url=url,
            created_at=photo.created_at,
        )

    async def create(self, *, user_id: UUID, taken_at: date, data: bytes) -> ProgressPhotoOut:
        if len(data) > MAX_PHOTO_BYTES:
            raise PhotoTooLargeError
        # Sniff the real type from the bytes — never trust the client's
        # declared Content-Type.
        sniffed = sniff_image(data)
        if sniffed is None:
            raise InvalidImageError
        content_type, ext = sniffed

        # Key is namespaced per user for tidiness, but authorization is by the
        # DB row's ownership, not by key secrecy.
        key = f"photos/{user_id}/{uuid4().hex}.{ext}"
        await self.storage.put(key=key, data=data, content_type=content_type)

        photo = await self.repo.create(
            user_id=user_id,
            taken_at=taken_at,
            storage_key=key,
            content_type=content_type,
            size_bytes=len(data),
        )
        await self.db.commit()
        return await self._to_out(photo)

    async def list_for_user(self, user_id: UUID) -> list[ProgressPhotoOut]:
        photos = await self.repo.list_for_user(user_id)
        return [await self._to_out(photo) for photo in photos]

    async def delete(self, *, user_id: UUID, photo_id: UUID) -> None:
        photo = await self.repo.get_by_id(photo_id)
        if photo is None or photo.user_id != user_id:
            raise PhotoNotFoundError
        # Remove the object first; if that fails we keep the row rather than
        # orphaning bytes in the bucket with no record.
        await self.storage.delete(key=photo.storage_key)
        await self.repo.delete(photo)
        await self.db.commit()
