from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ai_client, get_current_user
from app.core.config import get_settings
from app.core.rate_limit import ai_rate_limit, limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import (
    CoachMessageCreateRequest,
    CoachMessageOut,
    FoodParseRequest,
    FoodParseResponse,
)
from app.services.ai.client import AIClient
from app.services.ai.coach_service import CoachService
from app.services.ai.exceptions import AIOutputValidationError, AIProviderError
from app.services.ai.food_parser_service import FoodParserService

router = APIRouter(prefix="/ai", tags=["ai"])

_AI_DISABLED_DETAIL = (
    "AI features are not configured on this server. Core logging features "
    "(search, manual entry) work without them — see docs/ai-safety.md."
)


def _require_ai_client(ai_client: AIClient | None = Depends(get_ai_client)) -> AIClient:
    if ai_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_AI_DISABLED_DETAIL
        )
    return ai_client


@router.post("/parse-food", response_model=FoodParseResponse)
@limiter.limit(ai_rate_limit)
async def parse_food(
    request: Request,
    payload: FoodParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ai_client: AIClient = Depends(_require_ai_client),
) -> FoodParseResponse:
    settings = get_settings()
    try:
        items = await FoodParserService(db).parse(
            ai_client=ai_client,
            model=settings.ai_model_parsing,
            user_id=current_user.id,
            text=payload.text,
        )
    except AIOutputValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Could not understand that — try rephrasing, or log the food manually.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI food parsing is temporarily unavailable — log manually instead.",
        ) from exc
    return FoodParseResponse(items=items)


@router.post("/coach/messages", response_model=CoachMessageOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(ai_rate_limit)
async def send_coach_message(
    request: Request,
    payload: CoachMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ai_client: AIClient = Depends(_require_ai_client),
) -> CoachMessageOut:
    settings = get_settings()
    try:
        return await CoachService(db).send_message(
            ai_client=ai_client,
            model=settings.ai_model_coach,
            user_id=current_user.id,
            message=payload.message,
        )
    except AIOutputValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The coach couldn't produce a response — please try again.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI coach is temporarily unavailable.",
        ) from exc


@router.get("/coach/messages", response_model=list[CoachMessageOut])
async def list_coach_messages(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CoachMessageOut]:
    return await CoachService(db).list_history(current_user.id)


@router.delete("/coach/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_coach_messages(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await CoachService(db).clear_history(current_user.id)
