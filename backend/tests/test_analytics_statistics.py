"""Pure-function tests for the analytics maths.

No database and no HTTP: these are the rules that decide whether a number is
honest enough to show a user, so they are tested directly.
"""

from datetime import date, timedelta

import pytest

from app.services.analytics.statistics import (
    current_streak,
    exponential_moving_average,
    linear_fit,
    longest_streak,
    mean,
)


class TestLinearFit:
    def test_recovers_a_known_line(self) -> None:
        fit = linear_fit([0.0, 1.0, 2.0, 3.0], [10.0, 12.0, 14.0, 16.0])
        assert fit is not None
        assert fit.slope == pytest.approx(2.0)
        assert fit.intercept == pytest.approx(10.0)
        assert fit.r_squared == pytest.approx(1.0)

    def test_returns_none_without_two_points(self) -> None:
        assert linear_fit([1.0], [1.0]) is None
        assert linear_fit([], []) is None

    def test_returns_none_when_every_x_is_identical(self) -> None:
        # Several weigh-ins on one day define no rate of change. Reporting a
        # flat slope would claim the weight was stable over a period we have
        # no span for.
        assert linear_fit([5.0, 5.0, 5.0], [80.0, 81.0, 79.5]) is None

    def test_flat_data_is_a_perfect_flat_fit(self) -> None:
        fit = linear_fit([0.0, 1.0, 2.0], [80.0, 80.0, 80.0])
        assert fit is not None
        assert fit.slope == pytest.approx(0.0)
        assert fit.r_squared == pytest.approx(1.0)

    def test_noise_lowers_the_explained_variance(self) -> None:
        # This is what stops a confident rate being read off a scatter: the
        # same endpoints, but the points in between do not line up.
        clean = linear_fit([0.0, 1.0, 2.0, 3.0], [80.0, 79.5, 79.0, 78.5])
        noisy = linear_fit([0.0, 1.0, 2.0, 3.0], [80.0, 82.0, 76.0, 78.5])
        assert clean is not None and noisy is not None
        assert clean.r_squared > 0.99
        assert noisy.r_squared < 0.5

    def test_rejects_mismatched_lengths(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            linear_fit([1.0, 2.0], [1.0])


class TestExponentialMovingAverage:
    def test_seeds_on_the_first_value(self) -> None:
        # Seeding at zero would draw a weight chart climbing from 0 kg.
        smoothed = exponential_moving_average([80.0, 80.0, 80.0], 0.25)
        assert smoothed == [80.0, 80.0, 80.0]

    def test_lags_behind_a_step_change(self) -> None:
        smoothed = exponential_moving_average([80.0, 90.0], 0.25)
        assert smoothed[1] == pytest.approx(82.5)

    def test_alpha_of_one_is_a_passthrough(self) -> None:
        assert exponential_moving_average([1.0, 5.0, 2.0], 1.0) == [1.0, 5.0, 2.0]

    def test_rejects_an_out_of_range_alpha(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            exponential_moving_average([1.0], 0.0)

    def test_empty_input_gives_empty_output(self) -> None:
        assert exponential_moving_average([], 0.25) == []


class TestStreaks:
    def test_current_streak_counts_back_from_the_reference_day(self) -> None:
        today = date(2026, 9, 9)
        days = {today, today - timedelta(days=1), today - timedelta(days=2)}
        assert current_streak(days, ending=today) == 3

    def test_current_streak_is_zero_once_broken_today(self) -> None:
        # A run that ended yesterday is not a current streak, and quietly
        # reporting yesterday's would tell the user something untrue.
        today = date(2026, 9, 9)
        days = {today - timedelta(days=1), today - timedelta(days=2)}
        assert current_streak(days, ending=today) == 0

    def test_longest_streak_finds_the_best_run(self) -> None:
        start = date(2026, 9, 1)
        days = {start, start + timedelta(days=1)} | {
            start + timedelta(days=offset) for offset in (4, 5, 6, 7)
        }
        assert longest_streak(days) == 4

    def test_streaks_of_nothing_are_zero(self) -> None:
        assert longest_streak(set()) == 0
        assert current_streak(set(), ending=date(2026, 9, 9)) == 0


class TestMean:
    def test_rejects_an_empty_series(self) -> None:
        with pytest.raises(ValueError, match="no values"):
            mean([])

