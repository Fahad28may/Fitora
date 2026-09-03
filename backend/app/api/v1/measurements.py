from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.measurement_repository import MeasurementRepository
from app.schemas.measurement import BodyMeasurementCreateRequest, BodyMeasurementOut

router = APIRouter(prefix="/measurements", tags=["progress"])

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 30


@router.post("", response_model=BodyMeasurementOut, status_code=status.HTTP_201_CREATED)
async def create_measurement(
    payload: BodyMeasurementCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementOut:
    measurement = await MeasurementRepository(db).create(
        current_user.id, **payload.model_dump()
    )
    await db.commit()
    return BodyMeasurementOut.model_validate(measurement)


@router.get("", response_model=list[BodyMeasurementOut])
async def list_measurements(
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BodyMeasurementOut]:
    measurements = await MeasurementRepository(db).list_for_user(
        current_user.id, limit=limit, offset=offset
    )
    return [BodyMeasurementOut.model_validate(m) for m in measurements]


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement(
    measurement_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = MeasurementRepository(db)
    measurement = await repo.get_by_id(measurement_id)
    if measurement is None or measurement.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await repo.delete(measurement)
    await db.commit()
