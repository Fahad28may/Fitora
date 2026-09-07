from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.meal import MealCreateRequest, MealLogRequest, MealOut
from app.schemas.nutrition import FoodDiaryEntryOut
from app.services.meal_service import (
    MealFoodNotAccessibleError,
    MealNotFoundError,
    MealService,
)
from app.services.nutrition_service import MissingServingSizeError

router = APIRouter(prefix="/meals", tags=["nutrition"])


@router.post("", response_model=MealOut, status_code=status.HTTP_201_CREATED)
async def create_meal(
    payload: MealCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MealOut:
    """Save a reusable meal — "My Breakfast" and friends (§5)."""
    try:
        return await MealService(db).create(
            user_id=current_user.id,
            name=payload.name,
            items=[(i.food_id, i.quantity, i.unit.value) for i in payload.items],
        )
    except MealFoodNotAccessibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Food {exc.food_id} not found.",
        ) from exc
    except MissingServingSizeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "One of those foods has no serving size, so it can only be added by grams."
            ),
        ) from exc


@router.get("", response_model=list[MealOut])
async def list_meals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MealOut]:
    return await MealService(db).list_for_user(current_user.id)


@router.get("/{meal_id}", response_model=MealOut)
async def get_meal(
    meal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MealOut:
    try:
        return await MealService(db).get(user_id=current_user.id, meal_id=meal_id)
    except MealNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        ) from exc


@router.post(
    "/{meal_id}/log",
    response_model=list[FoodDiaryEntryOut],
    status_code=status.HTTP_201_CREATED,
)
async def log_meal(
    meal_id: UUID,
    payload: MealLogRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FoodDiaryEntryOut]:
    """Expand a saved meal into ordinary diary entries, one per item.

    The entries are independent of the template afterwards, so they can be
    edited or removed individually and later edits to the meal don't rewrite
    what was already logged.
    """
    try:
        return await MealService(db).log(
            user_id=current_user.id,
            meal_id=meal_id,
            logged_at=payload.logged_at,
            meal_category=payload.meal_category,
        )
    except MealNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        ) from exc


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(
    meal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deletes the template only. Anything already logged from it stays in the
    diary — it is a record of what the user ate."""
    try:
        await MealService(db).delete(user_id=current_user.id, meal_id=meal_id)
    except MealNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found"
        ) from exc
