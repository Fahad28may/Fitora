from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.exercise import ExerciseDifficulty, ExerciseType


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    muscle_groups: list[str]
    equipment: str | None
    instructions: str
    difficulty: ExerciseDifficulty
    exercise_type: ExerciseType
