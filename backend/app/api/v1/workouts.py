from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.workout_repository import WorkoutRepository
from app.schemas.workout import WorkoutCreateRequest, WorkoutOut
from app.schemas.workout_progress import ExerciseProgressionOut, WorkoutProgressOut
from app.services.workout_progress_service import (
    DEFAULT_WEEKS,
    MAX_WEEKS,
    WorkoutProgressService,
)
from app.services.workout_service import UnknownExerciseError, WorkoutService

router = APIRouter(prefix="/workouts", tags=["workouts"])


@router.post("", response_model=WorkoutOut, status_code=status.HTTP_201_CREATED)
async def create_workout(
    payload: WorkoutCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutOut:
    try:
        return await WorkoutService(db).create_workout(current_user.id, payload)
    except UnknownExerciseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown exercise: {exc.exercise_id}",
        ) from exc


@router.get("", response_model=list[WorkoutOut])
async def list_workouts(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[WorkoutOut]:
    return await WorkoutService(db).list_workouts(current_user.id)


# Declared before "/{workout_id}": FastAPI matches routes in declaration
# order, so a static path registered after the catch-all is unreachable.
@router.get("/progress", response_model=WorkoutProgressOut)
async def get_workout_progress(
    weeks: int = Query(default=DEFAULT_WEEKS, ge=1, le=MAX_WEEKS),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutProgressOut:
    """Personal records, training volume, and consistency over recent weeks."""
    return await WorkoutProgressService(db).get_progress(current_user.id, weeks)


@router.get("/progress/exercises/{exercise_id}", response_model=ExerciseProgressionOut)
async def get_exercise_progression(
    exercise_id: UUID,
    weeks: int = Query(default=DEFAULT_WEEKS, ge=1, le=MAX_WEEKS),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExerciseProgressionOut:
    """Heaviest set per week for one exercise — strength progression."""
    return await WorkoutProgressService(db).get_exercise_progression(
        current_user.id, exercise_id, weeks
    )


@router.get("/{workout_id}", response_model=WorkoutOut)
async def get_workout(
    workout_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutOut:
    repo = WorkoutRepository(db)
    workout = await repo.get_by_id(workout_id)
    if workout is None or workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    result = await WorkoutService(db).get_workout(workout_id)
    assert result is not None  # existence already confirmed above
    return result


@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout(
    workout_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = WorkoutRepository(db)
    workout = await repo.get_by_id(workout_id)
    if workout is None or workout.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    await repo.delete(workout)
    await db.commit()
