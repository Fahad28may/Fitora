from datetime import date as date_type

from pydantic import BaseModel


class DailyHistoryPoint(BaseModel):
    date: date_type
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    water_ml: int
    activity_minutes: int
    #: None (not 0) when nothing reported steps that day.
    steps: int | None


class HistoryOut(BaseModel):
    days: int
    since: date_type
    #: One point per day in the window, including days with nothing logged —
    #: skipping empty days would make gaps look like continuity.
    points: list[DailyHistoryPoint]
