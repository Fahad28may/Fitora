from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.goal import CalorieCalculationWarning, GoalCreateRequest, GoalOut
from app.services.goal_service import (
    GoalService,
    IncompleteProfileError,
    UnsafeGoalNotAcknowledgedError,
)

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalOut:
    service = GoalService(db)
    try:
        goal = await service.create_goal(
            user_id=current_user.id,
            goal_type=payload.goal_type.value,
            intensity=payload.intensity.value,
            current_weight_kg=payload.current_weight_kg,
            target_weight_kg=payload.target_weight_kg,
            acknowledge_risk=payload.acknowledge_risk,
        )
    except IncompleteProfileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete your profile (sex, height, date of birth, activity level) "
            "before setting a goal.",
        ) from exc
    except UnsafeGoalNotAcknowledgedError as exc:
        warning = CalorieCalculationWarning(
            is_safe=exc.result.is_safe,
            warnings=exc.result.warnings,
            safer_alternative_calories=exc.result.safer_alternative_calories,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=warning.model_dump(),
        ) from exc
    return GoalOut.model_validate(goal)


@router.get("/active", response_model=GoalOut | None)
async def get_active_goal(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> GoalOut | None:
    goal = await GoalService(db).get_active_goal(current_user.id)
    return GoalOut.model_validate(goal) if goal else None
