from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MAX_SINGLE_ENTRY_ML = 5000


class WaterEntryCreateRequest(BaseModel):
    logged_at: date
    amount_ml: int = Field(gt=0, le=MAX_SINGLE_ENTRY_ML)


class WaterEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    logged_at: date
    amount_ml: int
    created_at: datetime
