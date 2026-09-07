from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
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
from app.schemas.ai_actions import (
    ActionProposeRequest,
    ActionResultOut,
    ConfirmActionRequest,
    ProposedActionOut,
)
from app.schemas.ai_vision import PhotoRecognitionOut
from app.services.ai.action_service import AIActionService
from app.services.ai.client import AIClient
from app.services.ai.coach_service import CoachService
from app.services.ai.exceptions import AIOutputValidationError, AIProviderError
from app.services.ai.food_parser_service import FoodParserService
from app.services.ai.photo_recognition_service import PhotoRecognitionService
from app.services.food_diary_service import (
    FoodNotAccessibleError,
    FoodNotFoundError,
    MissingServingSizeError,
)
from app.services.storage.image_validation import MAX_PHOTO_BYTES, sniff_image

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


_VISION_DISABLED_DETAIL = (
    "Photo food recognition is not configured on this server. Search, manual "
    "entry, barcode and text description all work without it — see "
    "docs/ai-safety.md."
)


def _require_vision_model() -> str:
    """Photo recognition is separately switchable from the rest of AI: it is
    the only feature that sends a user's photograph to a third party, so an
    operator opts into it explicitly rather than getting it with the key."""
    settings = get_settings()
    if not settings.vision_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_VISION_DISABLED_DETAIL,
        )
    return settings.ai_model_vision


@router.post("/recognize-food", response_model=PhotoRecognitionOut)
@limiter.limit(ai_rate_limit)
async def recognize_food_photo(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ai_client: AIClient = Depends(_require_ai_client),
    vision_model: str = Depends(_require_vision_model),
) -> PhotoRecognitionOut:
    """Suggest foods visible in a photo (§7). Never logs anything.

    The image is read into memory, sent to the vision provider, and dropped
    when this request ends — it is not written to disk, not put in object
    storage, and not recorded against the user (§8). Nothing identifying the
    user is sent with it.
    """
    data = await file.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="That photo is too large — try a smaller one.",
        )
    # Sniff the real type from the bytes; never trust the declared
    # Content-Type, which is attacker-controlled.
    sniffed = sniff_image(data)
    if sniffed is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="That file isn't a JPEG, PNG or WebP image.",
        )
    content_type, _ = sniffed

    try:
        return await PhotoRecognitionService(db).recognize(
            ai_client=ai_client,
            model=vision_model,
            user_id=current_user.id,
            image_bytes=data,
            content_type=content_type,
        )
    except AIOutputValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Couldn't read that photo reliably — try a clearer one, or log "
                "the food by search instead."
            ),
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo recognition is temporarily unavailable — log manually instead.",
        ) from exc


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


@router.post("/actions/propose", response_model=ProposedActionOut)
@limiter.limit(ai_rate_limit)
async def propose_action(
    request: Request,
    payload: ActionProposeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ai_client: AIClient = Depends(_require_ai_client),
) -> ProposedActionOut:
    """Translate a natural-language request into a proposed action. This never
    writes anything — the client must call /actions/confirm to execute it."""
    settings = get_settings()
    try:
        return await AIActionService(db).propose(
            ai_client=ai_client,
            model=settings.ai_model_actions,
            user_id=current_user.id,
            message=payload.message,
        )
    except AIOutputValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Couldn't turn that into an action — try rephrasing, or do it manually.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI actions are temporarily unavailable — use the normal screens instead.",
        ) from exc


@router.post(
    "/actions/confirm",
    response_model=ActionResultOut,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_action(
    payload: ConfirmActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActionResultOut:
    """Execute a user-confirmed action. Deterministic — no AI is called here,
    so it works even if AI is disabled, and user_id comes from the session."""
    try:
        return await AIActionService(db).confirm(user_id=current_user.id, payload=payload)
    except (FoodNotFoundError, FoodNotAccessibleError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Food not found"
        ) from exc
    except MissingServingSizeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This food has no serving size on file — log it by grams instead.",
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
