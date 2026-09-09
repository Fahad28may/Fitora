from datetime import date as date_type
from enum import StrEnum

from pydantic import BaseModel


class Confidence(StrEnum):
    """How much weight a reader should put on a derived number.

    Present on every block that extrapolates rather than counts. §16 forbids
    fake precision, and the honest way to keep a thin-data estimate useful is
    to ship it labelled rather than to ship it bare.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class TrendDirection(StrEnum):
    FALLING = "falling"
    STEADY = "steady"
    RISING = "rising"


class WeightTrendPoint(BaseModel):
    date: date_type
    #: The day's logged weight (mean of that day's entries). Never interpolated
    #: — a day without a weigh-in produces no point at all rather than a made-up
    #: one, so the chart cannot imply data that was never recorded.
    weight_kg: float
    #: Smoothed trend value at this point.
    trend_kg: float


class GoalProjection(BaseModel):
    target_weight_kg: float
    estimated_weeks: float
    estimated_date: date_type
    caveat: str


class WeightTrendOut(BaseModel):
    available: bool
    #: Set when `available` is false: why there is no trend, in plain language.
    unavailable_reason: str | None = None
    points: list[WeightTrendPoint] = []
    entry_days: int = 0
    span_days: int = 0
    #: Rate of change from a least-squares fit, not from first-minus-last:
    #: two noisy endpoints can disagree wildly with the line through everything
    #: between them. None when the fit isn't defined.
    weekly_change_kg: float | None = None
    direction: TrendDirection | None = None
    #: Fraction of the weight variance the straight line explains (0–1).
    fit_quality: float | None = None
    confidence: Confidence | None = None
    #: Absent unless there is a goal weight *and* the trend is moving toward it
    #: at a rate worth extrapolating.
    goal_projection: GoalProjection | None = None
    projection_unavailable_reason: str | None = None


class TargetAdherence(BaseModel):
    """Days on target out of days that could be judged.

    Both numbers are returned rather than a percentage: "4 of 5 logged days" is
    a very different claim from "4 of 30 days", and a bare 80% hides which one
    it is.
    """

    days_on_target: int
    days_counted: int


class AdherenceOut(BaseModel):
    days_in_window: int
    days_food_logged: int
    current_streak_days: int
    longest_streak_days: int
    calories: TargetAdherence
    protein: TargetAdherence
    water: TargetAdherence
    #: False when there's no active goal — the three blocks above are then all
    #: zero-of-zero, because there is no target to be on.
    has_active_goal: bool


class MacroSplitOut(BaseModel):
    available: bool
    unavailable_reason: str | None = None
    days_counted: int = 0
    protein_percent: float | None = None
    carbs_percent: float | None = None
    fat_percent: float | None = None
    target_protein_percent: float | None = None
    target_carbs_percent: float | None = None
    target_fat_percent: float | None = None


class WeekdayPattern(BaseModel):
    #: 0 = Monday, matching `date.weekday()`.
    weekday: int
    label: str
    days_sampled: int
    #: None when nothing was logged on that weekday in the window. Zero would
    #: claim the user ate nothing; None says we don't know.
    avg_calories_kcal: float | None
    avg_activity_minutes: float | None


class EnergyBalanceOut(BaseModel):
    available: bool
    unavailable_reason: str | None = None
    days_counted: int = 0
    avg_intake_kcal: float | None = None
    #: Estimated from the profile (Mifflin-St Jeor × activity multiplier), the
    #: same deterministic path goal targets use.
    estimated_expenditure_kcal: int | None = None
    net_kcal: float | None = None
    #: Burn as reported by the user or their device, shown for context and
    #: deliberately *not* added to the estimate above — the activity multiplier
    #: already accounts for exercise, so summing the two would double-count it.
    reported_activity_burn_kcal: int | None = None
    note: str | None = None


class AnalyticsSummaryOut(BaseModel):
    generated_for: date_type
    since: date_type
    window_days: int
    weight_trend: WeightTrendOut
    adherence: AdherenceOut
    macro_split: MacroSplitOut
    weekday_patterns: list[WeekdayPattern]
    energy_balance: EnergyBalanceOut


class AdaptiveTargetBasis(BaseModel):
    """The evidence behind an adaptive suggestion, returned alongside it.

    A number that changes someone's daily calorie target should be auditable
    by the person it is aimed at, so the inputs travel with the output rather
    than staying on the server.
    """

    window_days: int
    span_days: int
    days_with_food_logged: int
    weigh_in_days: int
    avg_intake_kcal: float
    weight_change_kg: float


class AdaptiveTargetsOut(BaseModel):
    available: bool
    unavailable_reason: str | None = None
    confidence: Confidence | None = None
    #: Maintenance implied by the user's own intake and weight change.
    estimated_maintenance_kcal: int | None = None
    #: Maintenance predicted from the profile (Mifflin-St Jeor x activity
    #: level), shown next to the observed figure so the difference between a
    #: population equation and this person is visible rather than hidden.
    predicted_maintenance_kcal: int | None = None
    current_target_calories: int | None = None
    suggested_target_calories: int | None = None
    suggested_protein_g: int | None = None
    suggested_carbs_g: int | None = None
    suggested_fat_g: int | None = None
    delta_kcal: int | None = None
    basis: AdaptiveTargetBasis | None = None
    #: Always populated when a suggestion is present — including the standing
    #: reminder that nothing has been applied.
    caveats: list[str] = []
