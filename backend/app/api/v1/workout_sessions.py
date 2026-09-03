from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.workout_repository import WorkoutSessionRepository
from app.schemas.workout import WorkoutSessionCreateRequest, WorkoutSessionOut
from app.services.workout_service import UnknownExerciseError, WorkoutSessionService

router = APIRouter(prefix="/workout-sessions", tags=["workouts"])

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 30


@router.post("", response_model=WorkoutSessionOut, status_code=status.HTTP_201_CREATED)
async def log_workout_session(
    payload: WorkoutSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSessionOut:
    try:
        return await WorkoutSessionService(db).log_session(current_user.id, payload)
    except UnknownExerciseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown exercise: {exc.exercise_id}",
        ) from exc


@router.get("", response_model=list[WorkoutSessionOut])
async def list_workout_sessions(
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkoutSessionOut]:
    return await WorkoutSessionService(db).list_sessions(
        current_user.id, limit=limit, offset=offset
    )


@router.get("/{session_id}", response_model=WorkoutSessionOut)
async def get_workout_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutSessionOut:
    repo = WorkoutSessionRepository(db)
    session = await repo.get_by_id(session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    result = await WorkoutSessionService(db).get_session(session_id)
    assert result is not None  # existence already confirmed above
    return result


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = WorkoutSessionRepository(db)
    session = await repo.get_by_id(session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await repo.delete(session)
    await db.commit()
