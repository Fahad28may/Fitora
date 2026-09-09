from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.history import DailyHistoryPoint, HistoryOut
from app.services.daily_totals import collect_daily_totals

DEFAULT_DAYS = 30
MAX_DAYS = 90


class HistoryService:
    """Daily totals over a recent window, for the trend charts in §16.

    One endpoint rather than one per metric: the charts are read together on
    a single screen, and three round trips for three lines on the same axis
    would be worse for both the client and the database.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_history(self, user_id: UUID, days: int = DEFAULT_DAYS) -> HistoryOut:
        today = date.today()
        since = today - timedelta(days=days - 1)
        totals = await collect_daily_totals(self.db, user_id, since=since, until=today)

        # Every day in the window is emitted, including empty ones: a chart
        # that silently skips days you logged nothing would compress the
        # timeline and make gaps look like continuity.
        points: list[DailyHistoryPoint] = []
        for offset in range(days):
            day = since + timedelta(days=offset)
            points.append(
                DailyHistoryPoint(
                    date=day,
                    calories_kcal=round(totals.calories[day], 1),
                    protein_g=round(totals.protein[day], 1),
                    carbs_g=round(totals.carbs[day], 1),
                    fat_g=round(totals.fat[day], 1),
                    water_ml=totals.water_ml[day],
                    activity_minutes=totals.activity_minutes[day],
                    # None rather than 0 when nothing reported steps — the
                    # same distinction the dashboard makes.
                    steps=totals.steps[day] if day in totals.step_days else None,
                )
            )

        return HistoryOut(days=days, since=since, points=points)


__all__ = ["DEFAULT_DAYS", "MAX_DAYS", "HistoryService"]
