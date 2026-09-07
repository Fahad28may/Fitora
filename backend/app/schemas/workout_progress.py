from datetime import date
from uuid import UUID

from pydantic import BaseModel


class PersonalRecord(BaseModel):
    """The heaviest set actually performed for an exercise.

    Deliberately not an estimated one-rep max: an e1RM formula would report a
    weight the user has never lifted, which is exactly the fake precision §16
    warns against.
    """

    exercise_id: UUID
    exercise_name: str
    best_weight_kg: float
    reps_at_best: int
    achieved_at: date
    total_sets: int


class WeeklyVolume(BaseModel):
    week_start: date
    session_count: int
    set_count: int
    total_volume_kg: float


class WorkoutProgressOut(BaseModel):
    weeks: int
    since: date
    total_sessions: int
    total_volume_kg: float
    sessions_per_week: float
    active_weeks: int
    personal_records: list[PersonalRecord]
    #: One entry per week in the window, including weeks with no training —
    #: a gap is the most useful thing a consistency chart can show.
    weekly: list[WeeklyVolume]


class ExerciseProgressionPoint(BaseModel):
    week_start: date
    best_weight_kg: float
    reps_at_best: int


class ExerciseProgressionOut(BaseModel):
    exercise_id: UUID
    exercise_name: str
    weeks: int
    #: Only weeks the exercise was actually trained. Interpolating through
    #: untrained weeks would imply a strength level never demonstrated.
    points: list[ExerciseProgressionPoint]
