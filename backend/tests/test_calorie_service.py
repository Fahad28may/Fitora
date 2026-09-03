import pytest

from app.services.calorie_service import (
    MIN_SAFE_DAILY_CALORIES,
    ActivityLevel,
    GoalIntensity,
    GoalType,
    Sex,
    calculate_bmr,
    calculate_targets,
    calculate_tdee,
)


def test_bmr_male_matches_mifflin_st_jeor() -> None:
    bmr = calculate_bmr(sex=Sex.MALE, weight_kg=80, height_cm=180, age_years=30)
    assert bmr == pytest.approx(10 * 80 + 6.25 * 180 - 5 * 30 + 5)


def test_bmr_female_matches_mifflin_st_jeor() -> None:
    bmr = calculate_bmr(sex=Sex.FEMALE, weight_kg=65, height_cm=165, age_years=28)
    assert bmr == pytest.approx(10 * 65 + 6.25 * 165 - 5 * 28 - 161)


def test_tdee_applies_activity_multiplier() -> None:
    bmr = 1600
    assert calculate_tdee(bmr=bmr, activity_level=ActivityLevel.SEDENTARY) == pytest.approx(1920)
    assert calculate_tdee(bmr=bmr, activity_level=ActivityLevel.VERY_ACTIVE) == pytest.approx(3040)


def test_maintain_goal_targets_tdee() -> None:
    result = calculate_targets(
        sex=Sex.MALE,
        weight_kg=80,
        height_cm=180,
        age_years=30,
        activity_level=ActivityLevel.MODERATE,
        goal_type=GoalType.MAINTAIN_WEIGHT,
    )
    assert result.target_calories == result.tdee
    assert result.is_safe is True
    assert result.warnings == []


def test_lose_weight_standard_intensity_is_safe_for_typical_adult() -> None:
    result = calculate_targets(
        sex=Sex.FEMALE,
        weight_kg=75,
        height_cm=165,
        age_years=32,
        activity_level=ActivityLevel.LIGHT,
        goal_type=GoalType.LOSE_WEIGHT,
        intensity=GoalIntensity.STANDARD,
    )
    assert result.target_calories == result.tdee - 500
    assert result.is_safe is True


def test_lose_weight_aggressive_intensity_flagged_unsafe_when_rate_too_high() -> None:
    result = calculate_targets(
        sex=Sex.FEMALE,
        weight_kg=75,
        height_cm=165,
        age_years=32,
        activity_level=ActivityLevel.LIGHT,
        goal_type=GoalType.LOSE_WEIGHT,
        intensity=GoalIntensity.AGGRESSIVE,
    )
    assert result.is_safe is False
    assert result.warnings
    assert result.safer_alternative_calories is not None
    assert result.safer_alternative_calories > result.target_calories


def test_low_body_weight_extreme_deficit_flagged_unsafe_below_floor() -> None:
    # A small, sedentary person taking a large deficit can fall below the
    # absolute safe-calorie floor even at "standard" intensity.
    result = calculate_targets(
        sex=Sex.FEMALE,
        weight_kg=45,
        height_cm=150,
        age_years=25,
        activity_level=ActivityLevel.SEDENTARY,
        goal_type=GoalType.LOSE_WEIGHT,
        intensity=GoalIntensity.STANDARD,
    )
    assert result.target_calories < MIN_SAFE_DAILY_CALORIES
    assert result.is_safe is False
    assert any("minimum" in w for w in result.warnings)


def test_safer_alternative_is_itself_safe() -> None:
    unsafe = calculate_targets(
        sex=Sex.FEMALE,
        weight_kg=45,
        height_cm=150,
        age_years=25,
        activity_level=ActivityLevel.SEDENTARY,
        goal_type=GoalType.LOSE_WEIGHT,
        intensity=GoalIntensity.AGGRESSIVE,
    )
    assert unsafe.safer_alternative_calories is not None
    assert unsafe.safer_alternative_calories >= MIN_SAFE_DAILY_CALORIES


def test_macros_sum_approximately_to_target_calories() -> None:
    result = calculate_targets(
        sex=Sex.MALE,
        weight_kg=80,
        height_cm=180,
        age_years=30,
        activity_level=ActivityLevel.MODERATE,
        goal_type=GoalType.MAINTAIN_WEIGHT,
    )
    reconstructed = (
        result.macros.protein_g * 4 + result.macros.carbs_g * 4 + result.macros.fat_g * 9
    )
    assert reconstructed == pytest.approx(result.target_calories, abs=10)


def test_gain_weight_adds_surplus_to_tdee() -> None:
    result = calculate_targets(
        sex=Sex.MALE,
        weight_kg=70,
        height_cm=175,
        age_years=25,
        activity_level=ActivityLevel.ACTIVE,
        goal_type=GoalType.GAIN_WEIGHT,
        intensity=GoalIntensity.LIGHT,
    )
    assert result.target_calories == result.tdee + 250
    assert result.is_safe is True
