from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exercise import Exercise
from app.models.workout import WorkoutSession, WorkoutSet
from app.schemas.workout_progress import (
    ExerciseProgressionOut,
    ExerciseProgressionPoint,
    PersonalRecord,
    WeeklyVolume,
    WorkoutProgressOut,
)

DEFAULT_WEEKS = 12
MAX_WEEKS = 52


def _week_start(value: date) -> date:
    """Monday of the week containing `value`. ISO weeks so the buckets line up
    with how people talk about "this week"."""
    return value - timedelta(days=value.weekday())


def _as_date(value: datetime) -> date:
    # SQLite (tests) round-trips datetimes without tzinfo; treat naive as UTC
    # so bucketing matches what Postgres would produce.
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).date()
    return value.date()


class WorkoutProgressService:
    """Derived workout statistics (§14 "Progress").

    Everything here is computed from logged sets — nothing is stored or
    estimated. In particular a personal record is the heaviest weight actually
    lifted, not an estimated one-rep max: an estimate formula would invent
    precision the user never demonstrated (§16).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _sets_since(
        self, user_id: UUID, since: date
    ) -> list[tuple[WorkoutSet, WorkoutSession, Exercise]]:
        result = await self.db.execute(
            select(WorkoutSet, WorkoutSession, Exercise)
            .join(WorkoutSession, WorkoutSession.id == WorkoutSet.workout_session_id)
            .join(Exercise, Exercise.id == WorkoutSet.exercise_id)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= datetime(since.year, since.month, since.day),
            )
            .order_by(WorkoutSession.started_at)
        )
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def get_progress(self, user_id: UUID, weeks: int = DEFAULT_WEEKS) -> WorkoutProgressOut:
        today = date.today()
        since = _week_start(today) - timedelta(weeks=weeks - 1)
        rows = await self._sets_since(user_id, since)

        # --- personal records, per exercise ---
        best: dict[UUID, tuple[float, int, date, str]] = {}
        set_counts: dict[UUID, int] = defaultdict(int)
        for workout_set, session, exercise in rows:
            set_counts[exercise.id] += 1
            if workout_set.weight_kg is None:
                continue
            weight = float(workout_set.weight_kg)
            reps = workout_set.reps or 0
            performed = _as_date(session.started_at)
            current = best.get(exercise.id)
            # Heavier wins; at equal weight, more reps wins. Ties keep the
            # earlier date, so a PR reads as "when you first hit this".
            if current is None or (weight, reps) > (current[0], current[1]):
                best[exercise.id] = (weight, reps, performed, exercise.name)

        personal_records = [
            PersonalRecord(
                exercise_id=exercise_id,
                exercise_name=name,
                best_weight_kg=weight,
                reps_at_best=reps,
                achieved_at=achieved,
                total_sets=set_counts[exercise_id],
            )
            for exercise_id, (weight, reps, achieved, name) in best.items()
        ]
        personal_records.sort(key=lambda r: r.best_weight_kg, reverse=True)

        # --- weekly volume and frequency ---
        weekly_volume: dict[date, float] = defaultdict(float)
        weekly_sets: dict[date, int] = defaultdict(int)
        weekly_sessions: dict[date, set[UUID]] = defaultdict(set)
        for workout_set, session, _ in rows:
            bucket = _week_start(_as_date(session.started_at))
            weekly_sets[bucket] += 1
            weekly_sessions[bucket].add(session.id)
            if workout_set.weight_kg is not None and workout_set.reps is not None:
                weekly_volume[bucket] += float(workout_set.weight_kg) * workout_set.reps

        # Every week in the window is emitted, including empty ones: a gap is
        # the most useful thing a consistency chart can show, and omitting it
        # would silently compress the timeline.
        weekly: list[WeeklyVolume] = []
        bucket = _week_start(since)
        end = _week_start(today)
        while bucket <= end:
            weekly.append(
                WeeklyVolume(
                    week_start=bucket,
                    session_count=len(weekly_sessions.get(bucket, ())),
                    set_count=weekly_sets.get(bucket, 0),
                    total_volume_kg=round(weekly_volume.get(bucket, 0.0), 1),
                )
            )
            bucket += timedelta(weeks=1)

        active_weeks = sum(1 for w in weekly if w.session_count > 0)
        total_sessions = sum(w.session_count for w in weekly)

        return WorkoutProgressOut(
            weeks=weeks,
            since=since,
            total_sessions=total_sessions,
            total_volume_kg=round(sum(w.total_volume_kg for w in weekly), 1),
            sessions_per_week=round(total_sessions / len(weekly), 2) if weekly else 0.0,
            active_weeks=active_weeks,
            personal_records=personal_records,
            weekly=weekly,
        )

    async def get_exercise_progression(
        self, user_id: UUID, exercise_id: UUID, weeks: int = DEFAULT_WEEKS
    ) -> ExerciseProgressionOut:
        """Heaviest set per week for one exercise — the shape of strength
        progression over time.

        Only weeks the exercise was actually trained appear. Unlike the
        consistency chart above, interpolating a flat line through untrained
        weeks would imply a strength level that was never demonstrated.
        """
        today = date.today()
        since = _week_start(today) - timedelta(weeks=weeks - 1)
        rows = await self._sets_since(user_id, since)

        name = ""
        per_week: dict[date, tuple[float, int]] = {}
        for workout_set, session, exercise in rows:
            if exercise.id != exercise_id:
                continue
            name = exercise.name
            if workout_set.weight_kg is None:
                continue
            bucket = _week_start(_as_date(session.started_at))
            weight = float(workout_set.weight_kg)
            reps = workout_set.reps or 0
            current = per_week.get(bucket)
            if current is None or (weight, reps) > current:
                per_week[bucket] = (weight, reps)

        return ExerciseProgressionOut(
            exercise_id=exercise_id,
            exercise_name=name,
            weeks=weeks,
            points=[
                ExerciseProgressionPoint(
                    week_start=week, best_weight_kg=weight, reps_at_best=reps
                )
                for week, (weight, reps) in sorted(per_week.items())
            ],
        )


__all__ = ["DEFAULT_WEEKS", "MAX_WEEKS", "WorkoutProgressService"]
