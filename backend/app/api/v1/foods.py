from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.nutrition import Food, FoodNutrition
from app.models.user import User
from app.repositories.nutrition_repository import FoodRepository
from app.schemas.nutrition import FoodCreateRequest, FoodOut

router = APIRouter(prefix="/foods", tags=["nutrition"])

MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20
MIN_SEARCH_LENGTH = 2


def _to_food_out(food: Food, nutrition: FoodNutrition) -> FoodOut:
    return FoodOut(
        id=food.id,
        source=food.source,
        name=food.name,
        brand=food.brand,
        serving_description=food.serving_description,
        serving_grams=float(food.serving_grams) if food.serving_grams is not None else None,
        calories_kcal=float(nutrition.calories_kcal),
        protein_g=float(nutrition.protein_g),
        carbs_g=float(nutrition.carbs_g),
        fat_g=float(nutrition.fat_g),
        fiber_g=float(nutrition.fiber_g) if nutrition.fiber_g is not None else None,
    )


@router.get("/search", response_model=list[FoodOut])
async def search_foods(
    q: str = Query(min_length=MIN_SEARCH_LENGTH, max_length=200),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FoodOut]:
    results = await FoodRepository(db).search(
        user_id=current_user.id, query=q, limit=limit, offset=offset
    )
    return [_to_food_out(food, nutrition) for food, nutrition in results]


@router.post("", response_model=FoodOut, status_code=status.HTTP_201_CREATED)
async def create_custom_food(
    payload: FoodCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FoodOut:
    food = await FoodRepository(db).create_custom_food(
        owner_user_id=current_user.id, **payload.model_dump()
    )
    await db.commit()
    return FoodOut(
        id=food.id,
        source=food.source,
        name=food.name,
        brand=food.brand,
        serving_description=food.serving_description,
        serving_grams=float(food.serving_grams) if food.serving_grams is not None else None,
        calories_kcal=payload.calories_kcal,
        protein_g=payload.protein_g,
        carbs_g=payload.carbs_g,
        fat_g=payload.fat_g,
        fiber_g=payload.fiber_g,
    )


@router.get("/{food_id}", response_model=FoodOut)
async def get_food(
    food_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FoodOut:
    repo = FoodRepository(db)
    found = await repo.get_with_nutrition(food_id)
    if found is None or not await repo.is_readable_by(found[0], current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    return _to_food_out(*found)
