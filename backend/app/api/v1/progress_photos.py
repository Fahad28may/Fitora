from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_object_storage
from app.db.session import get_db
from app.models.user import User
from app.schemas.progress_photo import ProgressPhotoOut
from app.services.progress_photo_service import (
    InvalidImageError,
    PhotoNotFoundError,
    PhotoTooLargeError,
    ProgressPhotoService,
)
from app.services.storage.base import ObjectStorage, StorageError

router = APIRouter(prefix="/progress-photos", tags=["progress-photos"])

_STORAGE_DISABLED_DETAIL = (
    "Photo storage is not configured on this server. The rest of the app "
    "(nutrition, workouts, progress) works without it — see "
    "docs/third-party-services.md."
)


def _require_storage(
    storage: ObjectStorage | None = Depends(get_object_storage),
) -> ObjectStorage:
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_STORAGE_DISABLED_DETAIL
        )
    return storage


@router.post("", response_model=ProgressPhotoOut, status_code=status.HTTP_201_CREATED)
async def upload_progress_photo(
    file: UploadFile = File(...),
    taken_at: date | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(_require_storage),
) -> ProgressPhotoOut:
    data = await file.read()
    service = ProgressPhotoService(db, storage)
    try:
        return await service.create(
            user_id=current_user.id,
            taken_at=taken_at or datetime.now(UTC).date(),
            data=data,
        )
    except PhotoTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="That image is too large.",
        ) from exc
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="That file isn't a supported image (JPEG, PNG, or WebP).",
        ) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is temporarily unavailable — try again.",
        ) from exc


@router.get("", response_model=list[ProgressPhotoOut])
async def list_progress_photos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(_require_storage),
) -> list[ProgressPhotoOut]:
    return await ProgressPhotoService(db, storage).list_for_user(current_user.id)


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_progress_photo(
    photo_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(_require_storage),
) -> None:
    try:
        await ProgressPhotoService(db, storage).delete(
            user_id=current_user.id, photo_id=photo_id
        )
    except PhotoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is temporarily unavailable — try again.",
        ) from exc
