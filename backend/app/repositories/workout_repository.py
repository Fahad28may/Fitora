from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exercise import Exercise
from app.models.workout import (
    Workout,
    WorkoutExercise,
    WorkoutSession,
    WorkoutSet,
    WorkoutType,
)


class WorkoutRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID,
        name: str,
        workout_type: WorkoutType,
        exercises: list[dict[str, object]],
    ) -> Workout:
        workout = Workout(user_id=user_id, name=name, workout_type=workout_type)
        self.db.add(workout)
        await self.db.flush()

        for order_index, row in enumerate(exercises):
            self.db.add(
                WorkoutExercise(
                    workout_id=workout.id,
                    order_index=order_index,
                    **row,
                )
            )
        await self.db.flush()
        return workout

    async def list_for_user(self, user_id: UUID) -> list[Workout]:
        result = await self.db.execute(
            select(Workout).where(Workout.user_id == user_id).order_by(Workout.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, workout_id: UUID) -> Workout | None:
        result = await self.db.execute(select(Workout).where(Workout.id == workout_id))
        return result.scalar_one_or_none()

    async def get_exercises(
        self, workout_id: UUID
    ) -> list[tuple[WorkoutExercise, Exercise]]:
        stmt = (
            select(WorkoutExercise, Exercise)
            .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
            .where(WorkoutExercise.workout_id == workout_id)
            .order_by(WorkoutExercise.order_index)
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def delete(self, workout: Workout) -> None:
        await self.db.delete(workout)
        await self.db.flush()


class WorkoutSessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID,
        workout_id: UUID | None,
        started_at: datetime,
        ended_at: datetime,
        notes: str | None,
        sets: list[dict[str, object]],
    ) -> WorkoutSession:
        session = WorkoutSession(
            user_id=user_id,
            workout_id=workout_id,
            started_at=started_at,
            ended_at=ended_at,
            notes=notes,
        )
        self.db.add(session)
        await self.db.flush()

        for row in sets:
            self.db.add(WorkoutSet(workout_session_id=session.id, **row))
        await self.db.flush()
        return session

    async def list_for_user(
        self, user_id: UUID, *, limit: int, offset: int
    ) -> list[WorkoutSession]:
        result = await self.db.execute(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user_id)
            .order_by(WorkoutSession.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id(self, session_id: UUID) -> WorkoutSession | None:
        result = await self.db.execute(
            select(WorkoutSession).where(WorkoutSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_sets(self, session_id: UUID) -> list[tuple[WorkoutSet, Exercise]]:
        stmt = (
            select(WorkoutSet, Exercise)
            .join(Exercise, Exercise.id == WorkoutSet.exercise_id)
            .where(WorkoutSet.workout_session_id == session_id)
            .order_by(WorkoutSet.set_number)
        )
        result = await self.db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def delete(self, session: WorkoutSession) -> None:
        await self.db.delete(session)
        await self.db.flush()
