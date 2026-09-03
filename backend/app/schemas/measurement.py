from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_CM = 300


class BodyMeasurementCreateRequest(BaseModel):
    logged_at: date
    waist_cm: float | None = Field(default=None, gt=0, le=MAX_CM)
    chest_cm: float | None = Field(default=None, gt=0, le=MAX_CM)
    arm_cm: float | None = Field(default=None, gt=0, le=MAX_CM)
    leg_cm: float | None = Field(default=None, gt=0, le=MAX_CM)
    hip_cm: float | None = Field(default=None, gt=0, le=MAX_CM)

    @model_validator(mode="after")
    def _require_at_least_one_measurement(self) -> "BodyMeasurementCreateRequest":
        if not any(
            (self.waist_cm, self.chest_cm, self.arm_cm, self.leg_cm, self.hip_cm)
        ):
            raise ValueError("At least one measurement is required")
        return self


class BodyMeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    logged_at: date
    waist_cm: float | None
    chest_cm: float | None
    arm_cm: float | None
    leg_cm: float | None
    hip_cm: float | None
    created_at: datetime
