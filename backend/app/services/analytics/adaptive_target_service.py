"""Database glue for the adaptive-target proposal.

The arithmetic and every safety rule live in `adaptive_targets`; this class
only gathers the inputs and decides whether there is enough of them. Keeping
the split means the rules that bound a calorie suggestion can be tested
without a database.
"""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.profile_repository import GoalRepository, ProfileRepository
from app.repositories.weight_repository import WeightRepository
from app.schemas.analytics import AdaptiveTargetBasis, AdaptiveTargetsOut
from app.services.analytics.adaptive_targets import (
    COVERAGE_CAVEAT,
    DEFAULT_WINDOW_DAYS,
    MIN_FOOD_DAY_COVERAGE,
    MIN_FOOD_DAYS,
    MIN_SPAN_DAYS,
    MIN_WEIGH_IN_DAYS,
    PROPOSAL_CAVEAT,
    estimate_confidence,
    estimate_maintenance_kcal,
    is_plausible_maintenance,
    propose_target,
)
from app.services.analytics.analytics_service import estimated_expenditure_kcal
from app.services.analytics.statistics import linear_fit, mean
from app.services.calorie_service import GoalIntensity, GoalType, macros_for_calories
from app.services.daily_totals import collect_daily_totals

_NO_GOAL = (
    "Set a goal first - an adaptive target adjusts the goal you already have."
)
_NOT_ENOUGH_FOOD = (
    "Log food on at least {needed} days in this window. Adaptive targets are "
    "derived from what you actually ate, so sparse logging would move your "
    "target on the strength of guesswork."
)
_NOT_ENOUGH_WEIGH_INS = (
    "Weigh in on at least {needed} days spread over {span} days. A weight "
    "change measured from fewer readings is mostly hydration."
)
_IMPLAUSIBLE = (
    "Your logged intake and your weight change do not line up well enough to "
    "estimate from - that usually means some days were logged partially. Keep "
    "logging consistently for a couple of weeks and check back."
)


class AdaptiveTargetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.profiles = ProfileRepository(db)
        self.goals = GoalRepository(db)
        self.weights = WeightRepository(db)

    async def get_adaptive_targets(
        self, user_id: UUID, for_date: date, days: int = DEFAULT_WINDOW_DAYS
    ) -> AdaptiveTargetsOut:
        goal = await self.goals.get_active(user_id)
        if goal is None:
            return AdaptiveTargetsOut(available=False, unavailable_reason=_NO_GOAL)

        since = for_date - timedelta(days=days - 1)
        totals = await collect_daily_totals(self.db, user_id, since=since, until=for_date)

        food_days = sorted(totals.food_days)
        needed_food_days = max(MIN_FOOD_DAYS, round(days * MIN_FOOD_DAY_COVERAGE))
        if len(food_days) < needed_food_days:
            return AdaptiveTargetsOut(
                available=False,
                unavailable_reason=_NOT_ENOUGH_FOOD.format(needed=needed_food_days),
                current_target_calories=goal.target_calories,
            )

        weight_entries = await self.weights.list_for_user(
            user_id, date_from=since, date_to=for_date, limit=days * 5, offset=0
        )
        daily_weights: dict[date, list[float]] = {}
        for entry in weight_entries:
            daily_weights.setdefault(entry.logged_at, []).append(float(entry.weight_kg))

        weigh_in_days = sorted(daily_weights)
        span_days = (weigh_in_days[-1] - weigh_in_days[0]).days if weigh_in_days else 0
        if len(weigh_in_days) < MIN_WEIGH_IN_DAYS or span_days < MIN_SPAN_DAYS:
            return AdaptiveTargetsOut(
                available=False,
                unavailable_reason=_NOT_ENOUGH_WEIGH_INS.format(
                    needed=MIN_WEIGH_IN_DAYS, span=MIN_SPAN_DAYS
                ),
                current_target_calories=goal.target_calories,
            )

        # Weight change comes from the fitted line, not from first-minus-last:
        # half a kilo of endpoint noise over four weeks would move the
        # maintenance estimate by ~140 kcal/day, swamping the signal.
        offsets = [float((day - weigh_in_days[0]).days) for day in weigh_in_days]
        values = [mean(daily_weights[day]) for day in weigh_in_days]
        fit = linear_fit(offsets, values)
        if fit is None:  # pragma: no cover - a >=14 day span guarantees distinct x
            return AdaptiveTargetsOut(
                available=False,
                unavailable_reason=_NOT_ENOUGH_WEIGH_INS.format(
                    needed=MIN_WEIGH_IN_DAYS, span=MIN_SPAN_DAYS
                ),
                current_target_calories=goal.target_calories,
            )
        weight_change_kg = fit.slope * span_days

        # Intake is averaged over the same span the weight change was measured
        # across, so the two sides of the energy balance describe one period.
        intake_days = [
            day for day in food_days if weigh_in_days[0] <= day <= weigh_in_days[-1]
        ]
        if len(intake_days) < MIN_FOOD_DAYS:
            return AdaptiveTargetsOut(
                available=False,
                unavailable_reason=_NOT_ENOUGH_FOOD.format(needed=MIN_FOOD_DAYS),
                current_target_calories=goal.target_calories,
            )
        avg_intake = mean([totals.calories[day] for day in intake_days])

        estimate = estimate_maintenance_kcal(
            avg_intake_kcal=avg_intake,
            weight_change_kg=weight_change_kg,
            # +1 because a fit from day 0 to day 27 covers 28 days of eating.
            span_days=span_days + 1,
        )

        profile = await self.profiles.get(user_id)
        predicted = estimated_expenditure_kcal(profile, values[-1])

        basis = AdaptiveTargetBasis(
            window_days=days,
            span_days=estimate.span_days,
            days_with_food_logged=len(intake_days),
            weigh_in_days=len(weigh_in_days),
            avg_intake_kcal=estimate.avg_intake_kcal,
            weight_change_kg=estimate.weight_change_kg,
        )

        if not is_plausible_maintenance(estimate.maintenance_kcal, predicted):
            return AdaptiveTargetsOut(
                available=False,
                unavailable_reason=_IMPLAUSIBLE,
                predicted_maintenance_kcal=predicted,
                current_target_calories=goal.target_calories,
                basis=basis,
            )

        proposal = propose_target(
            maintenance_kcal=estimate.maintenance_kcal,
            goal_type=GoalType(goal.goal_type),
            intensity=GoalIntensity(goal.intensity),
            current_target_kcal=goal.target_calories,
        )
        macros = macros_for_calories(proposal.suggested_calories)

        return AdaptiveTargetsOut(
            available=True,
            confidence=estimate_confidence(
                span_days=estimate.span_days,
                food_days=len(intake_days),
                weigh_in_days=len(weigh_in_days),
            ),
            estimated_maintenance_kcal=estimate.maintenance_kcal,
            predicted_maintenance_kcal=predicted,
            current_target_calories=goal.target_calories,
            suggested_target_calories=proposal.suggested_calories,
            suggested_protein_g=macros.protein_g,
            suggested_carbs_g=macros.carbs_g,
            suggested_fat_g=macros.fat_g,
            delta_kcal=proposal.delta_from_current_kcal,
            basis=basis,
            caveats=[*proposal.warnings, COVERAGE_CAVEAT, PROPOSAL_CAVEAT],
        )


__all__ = ["AdaptiveTargetService"]
