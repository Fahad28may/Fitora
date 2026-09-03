from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.water_repository import WaterRepository
from app.schemas.water import WaterEntryCreateRequest, WaterEntryOut

router = APIRouter(prefix="/water-entries", tags=["water"])


@router.post("", response_model=WaterEntryOut, status_code=status.HTTP_201_CREATED)
async def create_water_entry(
    payload: WaterEntryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WaterEntryOut:
    entry = await WaterRepository(db).create(
        current_user.id, payload.logged_at, payload.amount_ml
    )
    await db.commit()
    return WaterEntryOut.model_validate(entry)


@router.get("", response_model=list[WaterEntryOut])
async def list_water_entries(
    logged_at: date = Query(default=None, alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WaterEntryOut]:
    resolved_date = logged_at or datetime.now(UTC).date()
    entries = await WaterRepository(db).list_for_day(current_user.id, resolved_date)
    return [WaterEntryOut.model_validate(entry) for entry in entries]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_water_entry(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = WaterRepository(db)
    entry = await repo.get_by_id(entry_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await repo.delete(entry)
    await db.commit()
