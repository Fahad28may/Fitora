from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.activity_entry import ActivitySource, ActivityType

MAX_DURATION_MIN = 1440  # 24h
MAX_DISTANCE_KM = 1000
MAX_STEPS = 200_000
MAX_CALORIES_BURNED = 20_000
MAX_NOTES_LEN = 500


class ActivityEntryCreateRequest(BaseModel):
    logged_at: date
    activity_type: ActivityType
    duration_min: int = Field(gt=0, le=MAX_DURATION_MIN)
    distance_km: float | None = Field(default=None, ge=0, le=MAX_DISTANCE_KM)
    steps: int | None = Field(default=None, ge=0, le=MAX_STEPS)
    calories_burned: int | None = Field(default=None, ge=0, le=MAX_CALORIES_BURNED)
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LEN)


class ActivityEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    logged_at: date
    activity_type: ActivityType
    duration_min: int
    distance_km: float | None
    steps: int | None
    calories_burned: int | None
    source: ActivitySource
    notes: str | None
    created_at: datetime
