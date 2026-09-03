from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.weight_repository import WeightRepository
from app.schemas.weight import WeightEntryCreateRequest, WeightEntryOut

router = APIRouter(prefix="/weight-entries", tags=["weight"])

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 30


@router.post("", response_model=WeightEntryOut, status_code=status.HTTP_201_CREATED)
async def create_weight_entry(
    payload: WeightEntryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeightEntryOut:
    repo = WeightRepository(db)
    entry = await repo.create(current_user.id, payload.logged_at, payload.weight_kg)
    await db.commit()
    return WeightEntryOut.model_validate(entry)


@router.get("", response_model=list[WeightEntryOut])
async def list_weight_entries(
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WeightEntryOut]:
    entries = await WeightRepository(db).list_for_user(
        current_user.id, date_from=date_from, date_to=date_to, limit=limit, offset=offset
    )
    return [WeightEntryOut.model_validate(entry) for entry in entries]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_weight_entry(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = WeightRepository(db)
    entry = await repo.get_by_id(entry_id)
    if entry is None or entry.user_id != current_user.id:
        # Same 404 whether the entry doesn't exist or belongs to someone
        # else — never confirm another user's resource IDs.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await repo.delete(entry)
    await db.commit()
