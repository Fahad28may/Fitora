from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WeightEntryCreateRequest(BaseModel):
    logged_at: date
    weight_kg: float = Field(gt=0, le=500)


class WeightEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    logged_at: date
    weight_kg: float
    created_at: datetime
