from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.exercise_repository import ExerciseRepository
from app.schemas.exercise import ExerciseOut

router = APIRouter(prefix="/exercises", tags=["workouts"])

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50


@router.get("", response_model=list[ExerciseOut])
async def list_exercises(
    q: str | None = Query(default=None, max_length=150),
    muscle_group: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExerciseOut]:
    exercises = await ExerciseRepository(db).search(
        query=q, muscle_group=muscle_group, limit=limit, offset=offset
    )
    return [ExerciseOut.model_validate(e) for e in exercises]


@router.get("/{exercise_id}", response_model=ExerciseOut)
async def get_exercise(
    exercise_id: UUID,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExerciseOut:
    exercise = await ExerciseRepository(db).get_by_id(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return ExerciseOut.model_validate(exercise)
