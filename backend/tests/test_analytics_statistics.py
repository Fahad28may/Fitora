"""Pure-function tests for the analytics maths and the adaptive-target rules.

No database and no HTTP: these are the rules that decide whether a number is
honest enough to show a user, so they are tested directly.
"""

from datetime import date, timedelta

import pytest

from app.schemas.analytics import Confidence
from app.services.analytics.adaptive_targets import (
    MAX_SINGLE_ADJUSTMENT_FRACTION,
    estimate_confidence,
    estimate_maintenance_kcal,
    is_plausible_maintenance,
    propose_target,
)
from app.services.analytics.statistics import (
    current_streak,
    exponential_moving_average,
    linear_fit,
    longest_streak,
    mean,
)
from app.services.calorie_service import (
    KCAL_PER_KG_BODYWEIGHT,
    MIN_SAFE_DAILY_CALORIES,
    GoalIntensity,
    GoalType,
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


class TestMaintenanceEstimate:
    def test_steady_weight_means_intake_is_maintenance(self) -> None:
        estimate = estimate_maintenance_kcal(
            avg_intake_kcal=2400, weight_change_kg=0.0, span_days=28
        )
        assert estimate.maintenance_kcal == 2400

    def test_losing_weight_implies_maintenance_above_intake(self) -> None:
        # 1 kg lost over 28 days is a deficit of 7700/28 = 275 kcal/day.
        estimate = estimate_maintenance_kcal(
            avg_intake_kcal=2000, weight_change_kg=-1.0, span_days=28
        )
        assert estimate.maintenance_kcal == round(2000 + KCAL_PER_KG_BODYWEIGHT / 28)

    def test_gaining_weight_implies_maintenance_below_intake(self) -> None:
        estimate = estimate_maintenance_kcal(
            avg_intake_kcal=3000, weight_change_kg=1.0, span_days=28
        )
        assert estimate.maintenance_kcal < 3000

    def test_rejects_a_zero_span(self) -> None:
        with pytest.raises(ValueError, match="span_days"):
            estimate_maintenance_kcal(
                avg_intake_kcal=2000, weight_change_kg=-1.0, span_days=0
            )


class TestPlausibility:
    def test_accepts_an_estimate_near_the_prediction(self) -> None:
        assert is_plausible_maintenance(2400, 2500)

    def test_rejects_a_physiologically_impossible_estimate(self) -> None:
        assert not is_plausible_maintenance(600, None)
        assert not is_plausible_maintenance(9000, None)

    def test_rejects_an_estimate_far_from_the_prediction(self) -> None:
        # The realistic cause is under-logging, not an extraordinary
        # metabolism — and acting on it would tell someone to eat far too little.
        assert not is_plausible_maintenance(1200, 2600)

    def test_falls_back_to_absolute_bounds_without_a_prediction(self) -> None:
        assert is_plausible_maintenance(1200, None)


class TestConfidence:
    def test_dense_long_history_is_high(self) -> None:
        assert (
            estimate_confidence(span_days=28, food_days=25, weigh_in_days=14)
            == Confidence.HIGH
        )

    def test_adequate_history_is_moderate(self) -> None:
        assert (
            estimate_confidence(span_days=21, food_days=15, weigh_in_days=6)
            == Confidence.MODERATE
        )

    def test_sparse_history_is_low(self) -> None:
        assert (
            estimate_confidence(span_days=28, food_days=12, weigh_in_days=3)
            == Confidence.LOW
        )


class TestProposeTarget:
    def test_cuts_from_observed_maintenance_when_losing(self) -> None:
        proposal = propose_target(
            maintenance_kcal=2600,
            goal_type=GoalType.LOSE_WEIGHT,
            intensity=GoalIntensity.STANDARD,
            current_target_kcal=2200,
        )
        assert proposal.suggested_calories == 2100
        assert proposal.delta_from_current_kcal == -100
        assert proposal.warnings == []

    def test_adds_to_observed_maintenance_when_gaining(self) -> None:
        proposal = propose_target(
            maintenance_kcal=2600,
            goal_type=GoalType.GAIN_WEIGHT,
            intensity=GoalIntensity.LIGHT,
            current_target_kcal=2800,
        )
        assert proposal.suggested_calories == 2850

    def test_maintaining_targets_maintenance_itself(self) -> None:
        proposal = propose_target(
            maintenance_kcal=2450,
            goal_type=GoalType.MAINTAIN_WEIGHT,
            intensity=GoalIntensity.STANDARD,
            current_target_kcal=2400,
        )
        assert proposal.suggested_calories == 2450

    def test_a_large_move_is_capped_and_explained(self) -> None:
        proposal = propose_target(
            maintenance_kcal=4000,
            goal_type=GoalType.MAINTAIN_WEIGHT,
            intensity=GoalIntensity.STANDARD,
            current_target_kcal=2000,
        )
        assert proposal.suggested_calories == round(2000 * (1 + MAX_SINGLE_ADJUSTMENT_FRACTION))
        assert any("at a time" in warning for warning in proposal.warnings)

    def test_never_proposes_below_the_safety_floor(self) -> None:
        # The step cap alone would allow 1120 here; the floor must still bite.
        proposal = propose_target(
            maintenance_kcal=1300,
            goal_type=GoalType.LOSE_WEIGHT,
            intensity=GoalIntensity.AGGRESSIVE,
            current_target_kcal=1400,
        )
        assert proposal.suggested_calories == MIN_SAFE_DAILY_CALORIES
        assert any(str(MIN_SAFE_DAILY_CALORIES) in warning for warning in proposal.warnings)
