"""Pure statistics helpers for the analytics endpoints.

No I/O, no ORM, no AI — same rule as `calorie_service`. Everything here is a
free function over plain numbers so the honesty rules in §16 ("avoid
misleading charts or fake precision") can be tested directly, without a
database or an HTTP client in the way.
"""

from dataclasses import dataclass
from datetime import date, timedelta

#: Smoothing constant for the weight trend line. 0.25 gives roughly a
#: two-week half-life at daily weigh-ins: heavy enough to hide the day-to-day
#: water swings that make a raw weight chart unreadable, light enough that a
#: real change shows up within days rather than weeks.
TREND_SMOOTHING_ALPHA = 0.25


@dataclass(frozen=True)
class LinearFit:
    """Least-squares fit of y over x, with the fraction of variance it explains.

    `r_squared` is what stops the app from reporting a confident rate of change
    off a scatter of noise: a slope through points that do not line up is a
    number, not a trend.
    """

    slope: float
    intercept: float
    r_squared: float


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("mean of no values")
    return sum(values) / len(values)


def linear_fit(xs: list[float], ys: list[float]) -> LinearFit | None:
    """Ordinary least squares. Returns None when a line is not defined —
    fewer than two points, or every x identical (a vertical line has no slope,
    and pretending it is flat would be a lie in either direction)."""
    if len(xs) != len(ys):
        raise ValueError("x and y must be the same length")
    n = len(xs)
    if n < 2:
        return None

    mean_x = mean(xs)
    mean_y = mean(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return None

    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    slope = covariance / var_x
    intercept = mean_y - slope * mean_x

    total_variance = sum((y - mean_y) ** 2 for y in ys)
    if total_variance == 0:
        # Every y identical: the fit is exact and the slope is 0. Reporting
        # r² = 1 here is correct — a flat line through flat data explains it.
        return LinearFit(slope=slope, intercept=intercept, r_squared=1.0)

    residuals = sum(
        (y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys, strict=True)
    )
    return LinearFit(
        slope=slope,
        intercept=intercept,
        r_squared=max(0.0, 1.0 - residuals / total_variance),
    )


def exponential_moving_average(values: list[float], alpha: float) -> list[float]:
    """EWMA seeded with the first value, one output per input.

    Seeding with the first observation rather than zero matters: a series that
    starts at 80 kg must not be drawn climbing up from 0 over its first week.
    """
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    smoothed: list[float] = []
    current: float | None = None
    for value in values:
        current = value if current is None else alpha * value + (1 - alpha) * current
        smoothed.append(current)
    return smoothed


def current_streak(days: set[date], *, ending: date) -> int:
    """Consecutive days with data, counting back from `ending` inclusive.

    Returns 0 when `ending` itself has no data — a streak that has already
    been broken today is not a streak, and quietly counting yesterday's would
    tell the user something that isn't true.
    """
    streak = 0
    cursor = ending
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(days: set[date]) -> int:
    """Longest run of consecutive days present in `days`."""
    if not days:
        return 0
    best = 0
    for day in days:
        if day - timedelta(days=1) in days:
            continue  # not the start of a run; it will be counted from its start
        run = 0
        cursor = day
        while cursor in days:
            run += 1
            cursor += timedelta(days=1)
        best = max(best, run)
    return best


__all__ = [
    "TREND_SMOOTHING_ALPHA",
    "LinearFit",
    "current_streak",
    "exponential_moving_average",
    "linear_fit",
    "longest_streak",
    "mean",
]
