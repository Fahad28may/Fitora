from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_food_db_client
from app.core.rate_limit import barcode_rate_limit, limiter
from app.db.session import get_db
from app.models.nutrition import Food, FoodNutrition
from app.models.user import User
from app.repositories.nutrition_repository import FoodRepository
from app.schemas.nutrition import FoodCreateRequest, FoodOut
from app.services.food_db.barcode_service import BarcodeLookupService
from app.services.food_db.client import FoodDbClient
from app.services.food_db.exceptions import (
    FoodDbProviderError,
    ProductNotFoundError,
    UnusableProductDataError,
)
from app.services.food_db.food_search_service import FoodSearchService

router = APIRouter(prefix="/foods", tags=["nutrition"])

MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20
MIN_SEARCH_LENGTH = 2

_EXTERNAL_SEARCH_DISABLED_DETAIL = (
    "Searching an external food database is not configured on this server. "
    "Local and custom foods still work - see docs/third-party-services.md."
)

_FOOD_DB_DISABLED_DETAIL = (
    "Barcode lookup is not configured on this server. Food search and manual "
    "entry work without it — see docs/third-party-services.md."
)


def _require_food_db_client(
    client: FoodDbClient | None = Depends(get_food_db_client),
) -> FoodDbClient:
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_FOOD_DB_DISABLED_DETAIL,
        )
    return client


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
@limiter.limit(barcode_rate_limit)
async def search_foods(
    request: Request,
    q: str = Query(min_length=MIN_SEARCH_LENGTH, max_length=200),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    include_external: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: FoodDbClient | None = Depends(get_food_db_client),
) -> list[FoodOut]:
    """Search foods, optionally extending the search to an external database.

    `include_external` defaults to false and must be asked for explicitly:
    unlike a barcode, the query is free text the user typed, so sending it to
    a third party is a disclosure the user should be making deliberately. The
    client is expected to present it that way rather than switching it on
    silently.
    """
    if include_external and client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_EXTERNAL_SEARCH_DISABLED_DETAIL,
        )

    service = FoodSearchService(db, client)
    try:
        results = await service.search(
            user_id=current_user.id,
            query=q,
            limit=limit,
            offset=offset,
            include_external=include_external,
        )
    except FoodDbProviderError:
        # Local results are the core feature and the provider is an extra, so
        # an outage degrades the search rather than failing it (§51).
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


@router.get("/barcode/{barcode}", response_model=FoodOut)
@limiter.limit(barcode_rate_limit)
async def lookup_food_by_barcode(
    request: Request,
    barcode: str = Path(pattern=r"^\d{6,14}$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: FoodDbClient = Depends(_require_food_db_client),
) -> FoodOut:
    """Resolve a scanned barcode to a food, fetching it from the configured
    food database on a cache miss.

    The result has `source == "external_db"`, which the client should use to
    show that the numbers come from a crowd-sourced database and are worth a
    glance against the package before logging.
    """
    try:
        food, nutrition = await BarcodeLookupService(db, client).lookup(barcode)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That barcode isn't in the food database — you can add it as a custom food.",
        ) from exc
    except UnusableProductDataError as exc:
        # Deliberately not a 404: the product exists, its nutrition data is
        # just not trustworthy enough to feed into calorie targets.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "That product's nutrition data is incomplete or implausible, so it "
                "wasn't imported — add it as a custom food from the label instead."
            ),
        ) from exc
    except FoodDbProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Barcode lookup is temporarily unavailable — try again or log manually.",
        ) from exc
    return _to_food_out(food, nutrition)


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
