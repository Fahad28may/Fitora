from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.dates import age_years
from app.models.profile import UnitSystem
from app.services.calorie_service import ActivityLevel, Sex

MIN_AGE_YEARS = 18
MAX_AGE_YEARS = 120


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    date_of_birth: date | None = None
    sex: Sex | None = None
    height_cm: float | None = Field(default=None, gt=0, le=300)
    activity_level: ActivityLevel | None = None
    unit_system: UnitSystem = UnitSystem.METRIC

    @field_validator("date_of_birth")
    @classmethod
    def _validate_age(cls, value: date | None) -> date | None:
        if value is None:
            return value
        age = age_years(value)
        if age < MIN_AGE_YEARS:
            raise ValueError(f"Fitora is currently for users aged {MIN_AGE_YEARS}+")
        if age > MAX_AGE_YEARS:
            raise ValueError("Please enter a valid date of birth")
        return value


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None
    date_of_birth: date | None
    sex: Sex | None
    height_cm: float | None
    activity_level: ActivityLevel | None
    unit_system: UnitSystem
