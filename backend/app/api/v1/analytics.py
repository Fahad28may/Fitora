from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import AdaptiveTargetsOut, AnalyticsSummaryOut
from app.services.analytics import adaptive_targets
from app.services.analytics.adaptive_target_service import AdaptiveTargetService
from app.services.analytics.analytics_service import (
    DEFAULT_WINDOW_DAYS,
    MAX_WINDOW_DAYS,
    MIN_WINDOW_DAYS,
    AnalyticsService,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def get_analytics_summary(
    for_date: date = Query(default=None, alias="date"),
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummaryOut:
    """Trends, adherence, and patterns over a recent window (§16).

    Deterministic — no AI involved. Blocks that lack the data to answer
    honestly return `available: false` with a plain-language reason instead of
    a number, rather than extrapolating from too little.
    """
    resolved_date = for_date or datetime.now(UTC).date()
    return await AnalyticsService(db).get_summary(current_user.id, resolved_date, days)


@router.get("/adaptive-targets", response_model=AdaptiveTargetsOut)
async def get_adaptive_targets(
    for_date: date = Query(default=None, alias="date"),
    days: int = Query(
        default=adaptive_targets.DEFAULT_WINDOW_DAYS,
        ge=adaptive_targets.MIN_WINDOW_DAYS,
        le=adaptive_targets.MAX_WINDOW_DAYS,
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdaptiveTargetsOut:
    """A calorie target proposed from the user's own intake and weight history.

    Read-only and advisory: it never writes a goal. Applying it means creating
    a new goal through `POST /goals`, which runs the full safety check — so the
    guardrails cannot be bypassed by way of this endpoint.
    """
    resolved_date = for_date or datetime.now(UTC).date()
    return await AdaptiveTargetService(db).get_adaptive_targets(
        current_user.id, resolved_date, days
    )
