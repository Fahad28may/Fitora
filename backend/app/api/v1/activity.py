from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_idempotency_key
from app.db.session import get_db
from app.models.activity_entry import ActivitySource
from app.models.user import User
from app.repositories.activity_repository import ActivityRepository
from app.schemas.activity import ActivityEntryCreateRequest, ActivityEntryOut
from app.services.idempotency_service import run_idempotent

router = APIRouter(prefix="/activity-entries", tags=["activity"])


@router.post("", response_model=ActivityEntryOut, status_code=status.HTTP_201_CREATED)
async def create_activity_entry(
    payload: ActivityEntryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Depends(get_idempotency_key),
) -> ActivityEntryOut:
    async def _create() -> ActivityEntryOut:
        # Manual logging only for now; device-sourced entries (Apple Health /
        # Health Connect / wearables) arrive via Phase 4 integrations, not here.
        entry = await ActivityRepository(db).create(
            user_id=current_user.id,
            logged_at=payload.logged_at,
            activity_type=payload.activity_type,
            duration_min=payload.duration_min,
            distance_km=payload.distance_km,
            steps=payload.steps,
            calories_burned=payload.calories_burned,
            source=ActivitySource.MANUAL,
            notes=payload.notes,
        )
        await db.commit()
        return ActivityEntryOut.model_validate(entry)

    return await run_idempotent(
        db,
        user_id=current_user.id,
        key=idempotency_key,
        endpoint="POST /activity-entries",
        status_code=status.HTTP_201_CREATED,
        model=ActivityEntryOut,
        produce=_create,
    )


@router.get("", response_model=list[ActivityEntryOut])
async def list_activity_entries(
    logged_at: date = Query(default=None, alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityEntryOut]:
    resolved_date = logged_at or datetime.now(UTC).date()
    entries = await ActivityRepository(db).list_for_day(current_user.id, resolved_date)
    return [ActivityEntryOut.model_validate(entry) for entry in entries]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity_entry(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = ActivityRepository(db)
    entry = await repo.get_by_id(entry_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await repo.delete(entry)
    await db.commit()
