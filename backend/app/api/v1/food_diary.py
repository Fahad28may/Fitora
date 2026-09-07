from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_idempotency_key
from app.db.session import get_db
from app.models.user import User
from app.repositories.nutrition_repository import FoodDiaryRepository
from app.schemas.nutrition import FoodDiaryEntryCreateRequest, FoodDiaryEntryOut
from app.services.food_diary_service import (
    FoodDiaryService,
    FoodNotAccessibleError,
    FoodNotFoundError,
    MissingServingSizeError,
)
from app.services.idempotency_service import run_idempotent

router = APIRouter(prefix="/food-diary", tags=["nutrition"])


@router.post("", response_model=FoodDiaryEntryOut, status_code=status.HTTP_201_CREATED)
async def create_diary_entry(
    payload: FoodDiaryEntryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> FoodDiaryEntryOut:
    service = FoodDiaryService(db)

    async def _create() -> FoodDiaryEntryOut:
        return await service.create_entry(
            user_id=current_user.id,
            food_id=payload.food_id,
            logged_at=payload.logged_at,
            meal_category=payload.meal_category.value,
            quantity=payload.quantity,
            unit=payload.unit.value,
            source=payload.source.value,
        )

    try:
        return await run_idempotent(
            db,
            user_id=current_user.id,
            key=idempotency_key,
            endpoint="POST /food-diary",
            status_code=status.HTTP_201_CREATED,
            model=FoodDiaryEntryOut,
            produce=_create,
        )
    except FoodNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Food not found"
        ) from exc
    except FoodNotAccessibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Food not found"
        ) from exc
    except MissingServingSizeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This food has no serving size on file — log it by grams instead.",
        ) from exc


@router.get("", response_model=list[FoodDiaryEntryOut])
async def list_diary_entries(
    logged_at: date = Query(alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FoodDiaryEntryOut]:
    return await FoodDiaryService(db).list_for_day(current_user.id, logged_at)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diary_entry(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = FoodDiaryRepository(db)
    entry = await repo.get_by_id(entry_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await repo.delete(entry)
    await db.commit()
