"""Advanced analytics (§16) — trends, adherence, and patterns.

Deterministic and rule-based, like `recommendation_service`: no LLM is
involved, and every block is allowed to answer "not enough data" instead of
producing a number. That refusal is the feature. A weekly rate of change
fitted through three noisy weigh-ins, or a goal date extrapolated from a week
of water weight, is precisely the "misleading chart / fake precision" §16
rules out.
"""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import age_years
from app.models.goal import Goal
from app.models.profile import UserProfile
from app.repositories.profile_repository import GoalRepository, ProfileRepository
from app.repositories.weight_repository import WeightRepository
from app.schemas.analytics import (
    AdherenceOut,
    AnalyticsSummaryOut,
    Confidence,
    EnergyBalanceOut,
    GoalProjection,
    MacroSplitOut,
    TargetAdherence,
    TrendDirection,
    WeekdayPattern,
    WeightTrendOut,
    WeightTrendPoint,
)
from app.services.analytics.statistics import (
    TREND_SMOOTHING_ALPHA,
    current_streak,
    exponential_moving_average,
    linear_fit,
    longest_streak,
    mean,
)
from app.services.calorie_service import (
    CARBS_KCAL_PER_GRAM,
    FAT_KCAL_PER_GRAM,
    PROTEIN_KCAL_PER_GRAM,
    ActivityLevel,
    Sex,
    calculate_bmr,
    calculate_tdee,
)
from app.services.daily_totals import DailyTotals, collect_daily_totals

DEFAULT_WINDOW_DAYS = 30
MIN_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 180

# A line needs two points; a *rate* worth reporting needs more than that, and
# needs them spread over enough time that daily fluctuation isn't the signal.
MIN_WEIGH_INS_FOR_RATE = 4
MIN_SPAN_DAYS_FOR_RATE = 14

# What it takes to call the fitted rate high-confidence rather than moderate.
HIGH_CONFIDENCE_WEIGH_INS = 12
HIGH_CONFIDENCE_SPAN_DAYS = 21
HIGH_CONFIDENCE_R_SQUARED = 0.5

#: Below this the trend is reported as steady rather than given a direction.
#: Scale noise alone easily produces a fitted rate this size.
STEADY_RATE_KG_PER_WEEK = 0.1

#: Projections beyond this are arithmetic, not forecasts.
MAX_PROJECTION_WEEKS = 104.0

#: How close to the goal weight counts as "there" — inside this, a projection
#: would be predicting noise.
GOAL_REACHED_TOLERANCE_KG = 0.5

# What counts as hitting a target on a given day.
CALORIE_ON_TARGET_TOLERANCE = 0.10
PROTEIN_ON_TARGET_FRACTION = 0.90
WATER_ON_TARGET_FRACTION = 0.90

#: Below this many logged days, averages over the window are not worth showing.
MIN_DAYS_FOR_AVERAGES = 3

_WEEKDAY_LABELS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

_ENERGY_BALANCE_NOTE = (
    "Expenditure is an estimate from your profile and activity level, not a "
    "measurement. Calories you or your device reported burning are shown "
    "separately and are not added on top - your activity level already "
    "accounts for exercise, so counting both would count it twice."
)


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.profiles = ProfileRepository(db)
        self.goals = GoalRepository(db)
        self.weights = WeightRepository(db)

    async def get_summary(
        self, user_id: UUID, for_date: date, days: int = DEFAULT_WINDOW_DAYS
    ) -> AnalyticsSummaryOut:
        since = for_date - timedelta(days=days - 1)
        totals = await collect_daily_totals(self.db, user_id, since=since, until=for_date)
        goal = await self.goals.get_active(user_id)
        profile = await self.profiles.get(user_id)

        daily_weights = await self._daily_weights(user_id, since=since, until=for_date)
        # The expenditure estimate needs a weight. The latest one in the window
        # is used rather than today's, so the estimate still works for a user
        # who weighs in weekly.
        latest_weight = (
            mean(daily_weights[max(daily_weights)]) if daily_weights else None
        )

        return AnalyticsSummaryOut(
            generated_for=for_date,
            since=since,
            window_days=days,
            weight_trend=self._weight_trend(daily_weights, goal),
            adherence=self._adherence(totals, goal, since=since, for_date=for_date, days=days),
            macro_split=self._macro_split(totals, goal),
            weekday_patterns=self._weekday_patterns(totals, since=since, days=days),
            energy_balance=self._energy_balance(totals, profile, latest_weight),
        )

    async def _daily_weights(
        self, user_id: UUID, *, since: date, until: date
    ) -> dict[date, list[float]]:
        # The limit is generous rather than exact: at most one weigh-in per day
        # matters once same-day entries are averaged, but a user who logs
        # several a day must not have the earliest days silently dropped.
        entries = await self.weights.list_for_user(
            user_id, date_from=since, date_to=until, limit=MAX_WINDOW_DAYS * 5, offset=0
        )
        daily: dict[date, list[float]] = {}
        for entry in entries:
            daily.setdefault(entry.logged_at, []).append(float(entry.weight_kg))
        return daily

    def _weight_trend(
        self, daily_weights: dict[date, list[float]], goal: Goal | None
    ) -> WeightTrendOut:
        if len(daily_weights) < 2:
            return WeightTrendOut(
                available=False,
                entry_days=len(daily_weights),
                unavailable_reason=(
                    "Log your weight on at least two days in this window to see a trend."
                ),
            )

        days = sorted(daily_weights)
        # Same-day entries are averaged rather than kept as separate points: a
        # morning and an evening weigh-in are two samples of one day, and
        # treating them as two days would distort the fitted rate.
        values = [mean(daily_weights[day]) for day in days]
        smoothed = exponential_moving_average(values, TREND_SMOOTHING_ALPHA)
        points = [
            WeightTrendPoint(date=day, weight_kg=round(value, 2), trend_kg=round(trend, 2))
            for day, value, trend in zip(days, values, smoothed, strict=True)
        ]
        span_days = (days[-1] - days[0]).days

        if len(days) < MIN_WEIGH_INS_FOR_RATE or span_days < MIN_SPAN_DAYS_FOR_RATE:
            # The line is drawable and honest; the *rate* is not, so it is
            # withheld rather than estimated from too little.
            return WeightTrendOut(
                available=True,
                points=points,
                entry_days=len(days),
                span_days=span_days,
                projection_unavailable_reason=(
                    f"A rate of change needs at least {MIN_WEIGH_INS_FOR_RATE} weigh-ins "
                    f"spread over {MIN_SPAN_DAYS_FOR_RATE} days."
                ),
            )

        offsets = [float((day - days[0]).days) for day in days]
        fit = linear_fit(offsets, values)
        if fit is None:  # pragma: no cover - a >=14 day span guarantees distinct x
            return WeightTrendOut(
                available=True, points=points, entry_days=len(days), span_days=span_days
            )

        weekly_change = fit.slope * 7
        confidence = self._rate_confidence(len(days), span_days, fit.r_squared)
        if abs(weekly_change) < STEADY_RATE_KG_PER_WEEK:
            direction = TrendDirection.STEADY
        elif weekly_change > 0:
            direction = TrendDirection.RISING
        else:
            direction = TrendDirection.FALLING

        projection, projection_reason = self._goal_projection(
            goal=goal,
            latest_trend_kg=smoothed[-1],
            latest_date=days[-1],
            weekly_change_kg=weekly_change,
            confidence=confidence,
        )

        return WeightTrendOut(
            available=True,
            points=points,
            entry_days=len(days),
            span_days=span_days,
            weekly_change_kg=round(weekly_change, 2),
            direction=direction,
            fit_quality=round(fit.r_squared, 2),
            confidence=confidence,
            goal_projection=projection,
            projection_unavailable_reason=projection_reason,
        )

    @staticmethod
    def _rate_confidence(weigh_ins: int, span_days: int, r_squared: float) -> Confidence:
        """Never LOW: a rate is only computed once the data clears the
        `MIN_WEIGH_INS_FOR_RATE`/`MIN_SPAN_DAYS_FOR_RATE` bar, and below that
        bar no rate is reported at all rather than one labelled low."""
        if (
            weigh_ins >= HIGH_CONFIDENCE_WEIGH_INS
            and span_days >= HIGH_CONFIDENCE_SPAN_DAYS
            and r_squared >= HIGH_CONFIDENCE_R_SQUARED
        ):
            return Confidence.HIGH
        return Confidence.MODERATE

    def _goal_projection(
        self,
        *,
        goal: Goal | None,
        latest_trend_kg: float,
        latest_date: date,
        weekly_change_kg: float,
        confidence: Confidence,
    ) -> tuple[GoalProjection | None, str | None]:
        """A date for reaching the goal weight, or the reason there isn't one.

        Every guard here exists to avoid printing a confident date the data
        cannot support: no goal weight, already there, not moving, moving the
        wrong way, or moving so slowly the arithmetic runs off the calendar.
        """
        if goal is None or goal.target_weight_kg is None:
            return None, "Set a goal weight to see a projection."

        target = float(goal.target_weight_kg)
        remaining = target - latest_trend_kg
        if abs(remaining) < GOAL_REACHED_TOLERANCE_KG:
            return None, "You're within half a kilo of your goal weight."
        if abs(weekly_change_kg) < STEADY_RATE_KG_PER_WEEK:
            return None, "Your weight is holding steady, so there's nothing to project from."
        if (remaining > 0) != (weekly_change_kg > 0):
            return None, "Your recent trend is moving away from your goal weight."

        weeks = remaining / weekly_change_kg
        if weeks > MAX_PROJECTION_WEEKS:
            return (
                None,
                "At the current rate this is more than two years out - too far to project.",
            )

        return (
            GoalProjection(
                target_weight_kg=target,
                estimated_weeks=round(weeks, 1),
                estimated_date=latest_date + timedelta(days=round(weeks * 7)),
                caveat=(
                    "An estimate from your recent trend, not a promise. Rates of change "
                    f"vary, and this one is {confidence.value} confidence."
                ),
            ),
            None,
        )

    def _adherence(
        self,
        totals: DailyTotals,
        goal: Goal | None,
        *,
        since: date,
        for_date: date,
        days: int,
    ) -> AdherenceOut:
        calories = TargetAdherence(days_on_target=0, days_counted=0)
        protein = TargetAdherence(days_on_target=0, days_counted=0)
        water = TargetAdherence(days_on_target=0, days_counted=0)

        if goal is not None:
            low = goal.target_calories * (1 - CALORIE_ON_TARGET_TOLERANCE)
            high = goal.target_calories * (1 + CALORIE_ON_TARGET_TOLERANCE)
            calorie_hits = sum(1 for day in totals.food_days if low <= totals.calories[day] <= high)
            protein_hits = sum(
                1
                for day in totals.food_days
                if totals.protein[day] >= goal.target_protein_g * PROTEIN_ON_TARGET_FRACTION
            )
            calories = TargetAdherence(
                days_on_target=calorie_hits, days_counted=len(totals.food_days)
            )
            protein = TargetAdherence(
                days_on_target=protein_hits, days_counted=len(totals.food_days)
            )

            # Counted over days water was logged, not over the whole window: a
            # day with no water entry is a day we know nothing about, not a
            # day the user drank nothing.
            water_hits = sum(
                1
                for day in totals.water_days
                if totals.water_ml[day] >= goal.target_water_ml * WATER_ON_TARGET_FRACTION
            )
            water = TargetAdherence(days_on_target=water_hits, days_counted=len(totals.water_days))

        # Streaks are computed over the requested window only, so the number
        # never claims more history than was asked for.
        in_window = {day for day in totals.food_days if since <= day <= for_date}
        return AdherenceOut(
            days_in_window=days,
            days_food_logged=len(in_window),
            current_streak_days=current_streak(in_window, ending=for_date),
            longest_streak_days=longest_streak(in_window),
            calories=calories,
            protein=protein,
            water=water,
            has_active_goal=goal is not None,
        )

    def _macro_split(self, totals: DailyTotals, goal: Goal | None) -> MacroSplitOut:
        if len(totals.food_days) < MIN_DAYS_FOR_AVERAGES:
            return MacroSplitOut(
                available=False,
                days_counted=len(totals.food_days),
                unavailable_reason=(
                    f"Log food on at least {MIN_DAYS_FOR_AVERAGES} days to see your macro split."
                ),
            )

        # Summed across the window rather than averaged per day, so a 300 kcal
        # day counts for 300 kcal and not for a whole day's worth of split.
        protein_kcal = sum(totals.protein[day] for day in totals.food_days) * PROTEIN_KCAL_PER_GRAM
        carbs_kcal = sum(totals.carbs[day] for day in totals.food_days) * CARBS_KCAL_PER_GRAM
        fat_kcal = sum(totals.fat[day] for day in totals.food_days) * FAT_KCAL_PER_GRAM
        macro_kcal = protein_kcal + carbs_kcal + fat_kcal
        if macro_kcal <= 0:
            return MacroSplitOut(
                available=False,
                days_counted=len(totals.food_days),
                unavailable_reason="The food you logged has no macros recorded.",
            )

        target_protein: float | None = None
        target_carbs: float | None = None
        target_fat: float | None = None
        if goal is not None:
            target_kcal = (
                goal.target_protein_g * PROTEIN_KCAL_PER_GRAM
                + goal.target_carbs_g * CARBS_KCAL_PER_GRAM
                + goal.target_fat_g * FAT_KCAL_PER_GRAM
            )
            if target_kcal > 0:
                target_protein = round(
                    goal.target_protein_g * PROTEIN_KCAL_PER_GRAM * 100 / target_kcal, 1
                )
                target_carbs = round(
                    goal.target_carbs_g * CARBS_KCAL_PER_GRAM * 100 / target_kcal, 1
                )
                target_fat = round(goal.target_fat_g * FAT_KCAL_PER_GRAM * 100 / target_kcal, 1)

        return MacroSplitOut(
            available=True,
            days_counted=len(totals.food_days),
            protein_percent=round(protein_kcal * 100 / macro_kcal, 1),
            carbs_percent=round(carbs_kcal * 100 / macro_kcal, 1),
            fat_percent=round(fat_kcal * 100 / macro_kcal, 1),
            target_protein_percent=target_protein,
            target_carbs_percent=target_carbs,
            target_fat_percent=target_fat,
        )

    def _weekday_patterns(
        self, totals: DailyTotals, *, since: date, days: int
    ) -> list[WeekdayPattern]:
        """Average intake and activity by day of the week.

        The pattern most people have and cannot see from a daily chart is a
        weekday/weekend split. Each weekday carries its own sample count so a
        single Saturday is not mistaken for a habit.
        """
        calories_by_weekday: dict[int, list[float]] = {index: [] for index in range(7)}
        minutes_by_weekday: dict[int, list[float]] = {index: [] for index in range(7)}
        for offset in range(days):
            day = since + timedelta(days=offset)
            if day in totals.food_days:
                calories_by_weekday[day.weekday()].append(totals.calories[day])
            if day in totals.activity_days:
                minutes_by_weekday[day.weekday()].append(float(totals.activity_minutes[day]))

        patterns: list[WeekdayPattern] = []
        for index in range(7):
            calories = calories_by_weekday[index]
            minutes = minutes_by_weekday[index]
            patterns.append(
                WeekdayPattern(
                    weekday=index,
                    label=_WEEKDAY_LABELS[index],
                    days_sampled=len(calories),
                    avg_calories_kcal=round(mean(calories), 1) if calories else None,
                    avg_activity_minutes=round(mean(minutes), 1) if minutes else None,
                )
            )
        return patterns

    def _energy_balance(
        self,
        totals: DailyTotals,
        profile: UserProfile | None,
        latest_weight_kg: float | None,
    ) -> EnergyBalanceOut:
        if len(totals.food_days) < MIN_DAYS_FOR_AVERAGES:
            return EnergyBalanceOut(
                available=False,
                days_counted=len(totals.food_days),
                unavailable_reason=(
                    f"Log food on at least {MIN_DAYS_FOR_AVERAGES} days to compare intake "
                    "with expenditure."
                ),
            )

        avg_intake = mean([totals.calories[day] for day in totals.food_days])
        reported_burn = (
            sum(totals.activity_burn_kcal[day] for day in totals.burn_days)
            if totals.burn_days
            else None
        )

        expenditure = estimated_expenditure_kcal(profile, latest_weight_kg)
        if expenditure is None:
            return EnergyBalanceOut(
                available=False,
                days_counted=len(totals.food_days),
                avg_intake_kcal=round(avg_intake, 1),
                reported_activity_burn_kcal=reported_burn,
                unavailable_reason=(
                    "Complete your profile - date of birth, sex, height, activity level - "
                    "and log your weight to estimate expenditure."
                ),
            )

        return EnergyBalanceOut(
            available=True,
            days_counted=len(totals.food_days),
            avg_intake_kcal=round(avg_intake, 1),
            estimated_expenditure_kcal=expenditure,
            net_kcal=round(avg_intake - expenditure, 1),
            reported_activity_burn_kcal=reported_burn,
            note=_ENERGY_BALANCE_NOTE,
        )


def estimated_expenditure_kcal(
    profile: UserProfile | None, weight_kg: float | None
) -> int | None:
    """TDEE from the profile, or None when the profile cannot support one.

    Deliberately the same deterministic path that sets goal targets: if the
    analytics disagreed with the targets about how much a user burns, one of
    the two would be wrong on every screen showing both.
    """
    if (
        profile is None
        or weight_kg is None
        or profile.sex is None
        or profile.height_cm is None
        or profile.date_of_birth is None
        or profile.activity_level is None
    ):
        return None
    bmr = calculate_bmr(
        sex=Sex(profile.sex),
        weight_kg=weight_kg,
        height_cm=float(profile.height_cm),
        age_years=age_years(profile.date_of_birth),
    )
    return round(calculate_tdee(bmr=bmr, activity_level=ActivityLevel(profile.activity_level)))


__all__ = [
    "DEFAULT_WINDOW_DAYS",
    "MAX_WINDOW_DAYS",
    "MIN_WINDOW_DAYS",
    "AnalyticsService",
    "estimated_expenditure_kcal",
]
