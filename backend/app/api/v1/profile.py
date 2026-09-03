from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.profile import UnitSystem
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import ProfileOut, ProfileUpdateRequest

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
async def get_profile(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ProfileOut:
    profile = await ProfileRepository(db).get(current_user.id)
    if profile is None:
        return ProfileOut(
            display_name=None,
            date_of_birth=None,
            sex=None,
            height_cm=None,
            activity_level=None,
            unit_system=UnitSystem.METRIC,
        )
    return ProfileOut.model_validate(profile)


@router.put("", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileOut:
    profile = await ProfileRepository(db).upsert(current_user.id, **payload.model_dump())
    await db.commit()
    return ProfileOut.model_validate(profile)
