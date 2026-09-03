from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.workout import WorkoutType


class WorkoutExerciseCreateRequest(BaseModel):
    exercise_id: UUID
    target_sets: int | None = Field(default=None, gt=0, le=50)
    target_reps: int | None = Field(default=None, gt=0, le=1000)
    target_weight_kg: float | None = Field(default=None, gt=0, le=500)


class WorkoutCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    workout_type: WorkoutType = WorkoutType.SINGLE
    exercises: list[WorkoutExerciseCreateRequest] = Field(min_length=1, max_length=50)


class WorkoutExerciseOut(BaseModel):
    id: UUID
    exercise_id: UUID
    exercise_name: str
    order_index: int
    target_sets: int | None
    target_reps: int | None
    target_weight_kg: float | None


class WorkoutOut(BaseModel):
    id: UUID
    name: str
    workout_type: WorkoutType
    created_at: datetime
    exercises: list[WorkoutExerciseOut]


class WorkoutSetCreateRequest(BaseModel):
    exercise_id: UUID
    set_number: int = Field(gt=0, le=50)
    reps: int | None = Field(default=None, gt=0, le=1000)
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    duration_seconds: int | None = Field(default=None, gt=0, le=86400)
    distance_m: float | None = Field(default=None, gt=0, le=1_000_000)
    rest_seconds: int | None = Field(default=None, ge=0, le=3600)
    notes: str | None = Field(default=None, max_length=500)


class WorkoutSessionCreateRequest(BaseModel):
    workout_id: UUID | None = None
    started_at: datetime
    ended_at: datetime
    notes: str | None = Field(default=None, max_length=1000)
    sets: list[WorkoutSetCreateRequest] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _ended_after_started(self) -> "WorkoutSessionCreateRequest":
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must not be before started_at")
        return self


class WorkoutSetOut(BaseModel):
    id: UUID
    exercise_id: UUID
    exercise_name: str
    set_number: int
    reps: int | None
    weight_kg: float | None
    duration_seconds: int | None
    distance_m: float | None
    rest_seconds: int | None
    notes: str | None


class WorkoutSessionOut(BaseModel):
    id: UUID
    workout_id: UUID | None
    started_at: datetime
    ended_at: datetime
    notes: str | None
    sets: list[WorkoutSetOut]
