from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardOut
from app.schemas.history import HistoryOut
from app.services.dashboard_service import DashboardService
from app.services.history_service import DEFAULT_DAYS, MAX_DAYS, HistoryService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def get_dashboard(
    for_date: date = Query(default=None, alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardOut:
    resolved_date = for_date or datetime.now(UTC).date()
    return await DashboardService(db).get_dashboard(current_user.id, resolved_date)


@router.get("/history", response_model=HistoryOut)
async def get_history(
    days: int = Query(default=DEFAULT_DAYS, ge=2, le=MAX_DAYS),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HistoryOut:
    """Daily totals over a recent window, for the trend charts (§16).

    One endpoint for every daily metric rather than one per chart: they are
    read together on a single screen.
    """
    return await HistoryService(db).get_history(current_user.id, days)
