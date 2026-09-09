"""Personalization: calorie targets re-estimated from what actually happened.

The goal targets in `calorie_service` come from Mifflin-St Jeor — a population
equation. It is a good starting point and a poor description of any particular
person: real maintenance varies by roughly +/-15% around the prediction. Once
a user has logged enough food and stepped on a scale enough times, their own
data says more about their maintenance calories than the equation does:

    maintenance = average intake - (weight change x 7700 kcal/kg / days)

This module turns that into a *proposal*. Nothing here writes a goal. The
estimate is clamped to the same safety floor as every other target (§11/§12),
capped in how far it may move an existing target in one step, and rejected
outright when it lands somewhere physiologically implausible — which in
practice means the user under-logged rather than that their metabolism is
extraordinary.
"""

from dataclasses import dataclass

from app.schemas.analytics import Confidence
from app.services.calorie_service import (
    INTENSITY_DAILY_KCAL_ADJUSTMENT,
    KCAL_PER_KG_BODYWEIGHT,
    MIN_SAFE_DAILY_CALORIES,
    GoalIntensity,
    GoalType,
)

#: Window over which intake and weight change are compared.
DEFAULT_WINDOW_DAYS = 28
MIN_WINDOW_DAYS = 14
MAX_WINDOW_DAYS = 90

# Data floors. Two weeks is the shortest span over which a weight change is
# signal rather than hydration; below 60% logging coverage the "unlogged days
# looked like logged days" assumption stops being reasonable.
MIN_SPAN_DAYS = 14
MIN_WEIGH_IN_DAYS = 4
MIN_FOOD_DAYS = 10
MIN_FOOD_DAY_COVERAGE = 0.6

# Thresholds for calling the estimate high rather than moderate confidence.
HIGH_CONFIDENCE_SPAN_DAYS = 28
HIGH_CONFIDENCE_COVERAGE = 0.8
HIGH_CONFIDENCE_WEIGH_IN_DAYS = 12

# An estimate outside this band is not a metabolism, it is a logging artefact.
MIN_PLAUSIBLE_MAINTENANCE_KCAL = 1000
MAX_PLAUSIBLE_MAINTENANCE_KCAL = 6000

#: How far the observed estimate may sit from the profile prediction before it
#: is treated as an artefact. Genuine individual variation is well inside this.
MAX_DIVERGENCE_FROM_PREDICTED = 0.40

#: A single proposal may move an existing target by at most this fraction.
#: Estimates carry real noise, and a target that lurches on every refresh is
#: worse guidance than one that converges over a few weeks.
MAX_SINGLE_ADJUSTMENT_FRACTION = 0.20

COVERAGE_CAVEAT = (
    "This assumes the days you did not log looked like the days you did. If you "
    "logged your lighter days more carefully than your heavier ones, the estimate "
    "will read low."
)
PROPOSAL_CAVEAT = (
    "Nothing changes until you set a new goal yourself - this is a suggestion "
    "based on your own data, not an adjustment that has been applied."
)


@dataclass(frozen=True)
class MaintenanceEstimate:
    maintenance_kcal: int
    avg_intake_kcal: float
    weight_change_kg: float
    span_days: int


@dataclass(frozen=True)
class TargetProposal:
    suggested_calories: int
    delta_from_current_kcal: int
    warnings: list[str]


def estimate_maintenance_kcal(
    *, avg_intake_kcal: float, weight_change_kg: float, span_days: int
) -> MaintenanceEstimate:
    """Energy balance, solved for maintenance.

    `weight_change_kg` should come from a fitted trend rather than from
    subtracting two weigh-ins: endpoint noise of half a kilo over four weeks
    moves this estimate by ~140 kcal/day, which is most of the signal.
    """
    if span_days <= 0:
        raise ValueError("span_days must be positive")
    daily_surplus = weight_change_kg * KCAL_PER_KG_BODYWEIGHT / span_days
    return MaintenanceEstimate(
        maintenance_kcal=round(avg_intake_kcal - daily_surplus),
        avg_intake_kcal=round(avg_intake_kcal, 1),
        weight_change_kg=round(weight_change_kg, 2),
        span_days=span_days,
    )


def is_plausible_maintenance(
    maintenance_kcal: int, predicted_tdee_kcal: int | None
) -> bool:
    """Whether an estimate is worth showing at all.

    Two independent checks: absolute physiological bounds, and — when the
    profile supports a prediction — agreement with it to within
    `MAX_DIVERGENCE_FROM_PREDICTED`. A user whose data implies they maintain on
    900 kcal has under-logged; telling them to eat 900 would be actively
    harmful, so the estimate is withheld rather than shown with a warning.
    """
    if not (
        MIN_PLAUSIBLE_MAINTENANCE_KCAL <= maintenance_kcal <= MAX_PLAUSIBLE_MAINTENANCE_KCAL
    ):
        return False
    if predicted_tdee_kcal is None or predicted_tdee_kcal <= 0:
        return True
    divergence = abs(maintenance_kcal - predicted_tdee_kcal) / predicted_tdee_kcal
    return divergence <= MAX_DIVERGENCE_FROM_PREDICTED


def estimate_confidence(
    *, span_days: int, food_days: int, weigh_in_days: int
) -> Confidence:
    coverage = food_days / span_days if span_days else 0.0
    if (
        span_days >= HIGH_CONFIDENCE_SPAN_DAYS
        and coverage >= HIGH_CONFIDENCE_COVERAGE
        and weigh_in_days >= HIGH_CONFIDENCE_WEIGH_IN_DAYS
    ):
        return Confidence.HIGH
    if coverage >= MIN_FOOD_DAY_COVERAGE and weigh_in_days >= MIN_WEIGH_IN_DAYS:
        return Confidence.MODERATE
    return Confidence.LOW


def propose_target(
    *,
    maintenance_kcal: int,
    goal_type: GoalType,
    intensity: GoalIntensity,
    current_target_kcal: int,
) -> TargetProposal:
    """Turn a maintenance estimate into a safe, bounded target suggestion."""
    adjustment = INTENSITY_DAILY_KCAL_ADJUSTMENT[intensity]
    if goal_type == GoalType.LOSE_WEIGHT:
        raw = maintenance_kcal - adjustment
    elif goal_type == GoalType.GAIN_WEIGHT:
        raw = maintenance_kcal + adjustment
    else:
        raw = maintenance_kcal

    warnings: list[str] = []

    lower_step = round(current_target_kcal * (1 - MAX_SINGLE_ADJUSTMENT_FRACTION))
    upper_step = round(current_target_kcal * (1 + MAX_SINGLE_ADJUSTMENT_FRACTION))
    stepped = min(max(raw, lower_step), upper_step)
    if stepped != raw:
        warnings.append(
            "Your data suggests a bigger change than this. Targets move by at most "
            f"{round(MAX_SINGLE_ADJUSTMENT_FRACTION * 100)}% at a time, so check back in "
            "a few weeks and adjust again if the trend holds."
        )

    suggested = stepped
    if suggested < MIN_SAFE_DAILY_CALORIES:
        suggested = MIN_SAFE_DAILY_CALORIES
        warnings.append(
            f"Raised to the {MIN_SAFE_DAILY_CALORIES} kcal/day floor. Eating below that "
            "is not supported here - speak to a qualified healthcare professional if you "
            "believe you need to."
        )

    return TargetProposal(
        suggested_calories=suggested,
        delta_from_current_kcal=suggested - current_target_kcal,
        warnings=warnings,
    )


__all__ = [
    "COVERAGE_CAVEAT",
    "DEFAULT_WINDOW_DAYS",
    "MAX_WINDOW_DAYS",
    "MIN_FOOD_DAYS",
    "MIN_FOOD_DAY_COVERAGE",
    "MIN_SPAN_DAYS",
    "MIN_WEIGH_IN_DAYS",
    "MIN_WINDOW_DAYS",
    "PROPOSAL_CAVEAT",
    "MaintenanceEstimate",
    "TargetProposal",
    "estimate_confidence",
    "estimate_maintenance_kcal",
    "is_plausible_maintenance",
    "propose_target",
]
