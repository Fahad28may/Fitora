from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exercise import Exercise
from app.models.workout import Workout, WorkoutExercise, WorkoutSession, WorkoutSet, WorkoutType
from app.repositories.exercise_repository import ExerciseRepository
from app.repositories.workout_repository import WorkoutRepository, WorkoutSessionRepository
from app.schemas.workout import (
    WorkoutCreateRequest,
    WorkoutExerciseOut,
    WorkoutOut,
    WorkoutSessionCreateRequest,
    WorkoutSessionOut,
    WorkoutSetOut,
)


class UnknownExerciseError(Exception):
    def __init__(self, exercise_id: UUID) -> None:
        self.exercise_id = exercise_id
        super().__init__(f"Unknown exercise: {exercise_id}")


def _workout_to_out(
    workout: Workout, rows: list[tuple[WorkoutExercise, Exercise]]
) -> WorkoutOut:
    return WorkoutOut(
        id=workout.id,
        name=workout.name,
        workout_type=workout.workout_type,
        created_at=workout.created_at,
        exercises=[
            WorkoutExerciseOut(
                id=we.id,
                exercise_id=exercise.id,
                exercise_name=exercise.name,
                order_index=we.order_index,
                target_sets=we.target_sets,
                target_reps=we.target_reps,
                target_weight_kg=float(we.target_weight_kg)
                if we.target_weight_kg is not None
                else None,
            )
            for we, exercise in rows
        ],
    )


def _session_to_out(
    session: WorkoutSession, rows: list[tuple[WorkoutSet, Exercise]]
) -> WorkoutSessionOut:
    return WorkoutSessionOut(
        id=session.id,
        workout_id=session.workout_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        notes=session.notes,
        sets=[
            WorkoutSetOut(
                id=s.id,
                exercise_id=exercise.id,
                exercise_name=exercise.name,
                set_number=s.set_number,
                reps=s.reps,
                weight_kg=float(s.weight_kg) if s.weight_kg is not None else None,
                duration_seconds=s.duration_seconds,
                distance_m=float(s.distance_m) if s.distance_m is not None else None,
                rest_seconds=s.rest_seconds,
                notes=s.notes,
            )
            for s, exercise in rows
        ],
    )


class WorkoutService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.workouts = WorkoutRepository(db)
        self.exercises = ExerciseRepository(db)

    async def _assert_exercises_exist(self, exercise_ids: list[UUID]) -> None:
        for exercise_id in set(exercise_ids):
            if await self.exercises.get_by_id(exercise_id) is None:
                raise UnknownExerciseError(exercise_id)

    async def create_workout(self, user_id: UUID, payload: WorkoutCreateRequest) -> WorkoutOut:
        await self._assert_exercises_exist([e.exercise_id for e in payload.exercises])
        workout = await self.workouts.create(
            user_id=user_id,
            name=payload.name,
            workout_type=payload.workout_type,
            exercises=[e.model_dump() for e in payload.exercises],
        )
        await self.db.commit()
        rows = await self.workouts.get_exercises(workout.id)
        return _workout_to_out(workout, rows)

    async def get_workout(self, workout_id: UUID) -> WorkoutOut | None:
        workout = await self.workouts.get_by_id(workout_id)
        if workout is None:
            return None
        rows = await self.workouts.get_exercises(workout_id)
        return _workout_to_out(workout, rows)

    async def list_workouts(self, user_id: UUID) -> list[WorkoutOut]:
        workouts = await self.workouts.list_for_user(user_id)
        out = []
        for workout in workouts:
            rows = await self.workouts.get_exercises(workout.id)
            out.append(_workout_to_out(workout, rows))
        return out


class WorkoutSessionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sessions = WorkoutSessionRepository(db)
        self.exercises = ExerciseRepository(db)

    async def _assert_exercises_exist(self, exercise_ids: list[UUID]) -> None:
        for exercise_id in set(exercise_ids):
            if await self.exercises.get_by_id(exercise_id) is None:
                raise UnknownExerciseError(exercise_id)

    async def log_session(
        self, user_id: UUID, payload: WorkoutSessionCreateRequest
    ) -> WorkoutSessionOut:
        await self._assert_exercises_exist([s.exercise_id for s in payload.sets])
        session = await self.sessions.create(
            user_id=user_id,
            workout_id=payload.workout_id,
            started_at=payload.started_at,
            ended_at=payload.ended_at,
            notes=payload.notes,
            sets=[s.model_dump() for s in payload.sets],
        )
        await self.db.commit()
        rows = await self.sessions.get_sets(session.id)
        return _session_to_out(session, rows)

    async def get_session(self, session_id: UUID) -> WorkoutSessionOut | None:
        session = await self.sessions.get_by_id(session_id)
        if session is None:
            return None
        rows = await self.sessions.get_sets(session_id)
        return _session_to_out(session, rows)

    async def list_sessions(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> list[WorkoutSessionOut]:
        sessions = await self.sessions.list_for_user(user_id, limit=limit, offset=offset)
        out = []
        for session in sessions:
            rows = await self.sessions.get_sets(session.id)
            out.append(_session_to_out(session, rows))
        return out


__all__ = [
    "UnknownExerciseError",
    "WorkoutService",
    "WorkoutSessionService",
    "WorkoutType",
]
