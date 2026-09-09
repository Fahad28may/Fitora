"""Deterministic BMR/TDEE/calorie-target calculation.

Pure functions only — no I/O, no AI calls. Per docs/ai-safety.md §"No AI
dependency for core data", the LLM is never asked to compute these values.
"""

from dataclasses import dataclass, field
from enum import StrEnum

MIN_SAFE_DAILY_CALORIES = 1200
MAX_SAFE_WEEKLY_RATE_KG = 0.75  # roughly 1% bodyweight/week for most adults

PROTEIN_KCAL_PER_GRAM = 4
CARBS_KCAL_PER_GRAM = 4
FAT_KCAL_PER_GRAM = 9

PROTEIN_CALORIE_SHARE = 0.30
CARBS_CALORIE_SHARE = 0.40
FAT_CALORIE_SHARE = 0.30


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(StrEnum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}


class GoalType(StrEnum):
    LOSE_WEIGHT = "lose_weight"
    MAINTAIN_WEIGHT = "maintain_weight"
    GAIN_WEIGHT = "gain_weight"


class GoalIntensity(StrEnum):
    LIGHT = "light"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"


# kcal/day adjustment from TDEE, and the approximate weekly rate of bodyweight
# change it implies (~7700 kcal per kg of bodyweight).
INTENSITY_DAILY_KCAL_ADJUSTMENT: dict[GoalIntensity, int] = {
    GoalIntensity.LIGHT: 250,
    GoalIntensity.STANDARD: 500,
    GoalIntensity.AGGRESSIVE: 1000,
}

KCAL_PER_KG_BODYWEIGHT = 7700


@dataclass(frozen=True)
class MacroTargets:
    protein_g: int
    carbs_g: int
    fat_g: int


@dataclass(frozen=True)
class CalorieTargetResult:
    bmr: int
    tdee: int
    target_calories: int
    macros: MacroTargets
    is_safe: bool
    warnings: list[str] = field(default_factory=list)
    safer_alternative_calories: int | None = None


def calculate_bmr(*, sex: Sex, weight_kg: float, height_cm: float, age_years: int) -> float:
    """Mifflin-St Jeor equation."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age_years
    return base + (5 if sex == Sex.MALE else -161)


def calculate_tdee(*, bmr: float, activity_level: ActivityLevel) -> float:
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]


def macros_for_calories(calories: int) -> MacroTargets:
    return MacroTargets(
        protein_g=round(calories * PROTEIN_CALORIE_SHARE / PROTEIN_KCAL_PER_GRAM),
        carbs_g=round(calories * CARBS_CALORIE_SHARE / CARBS_KCAL_PER_GRAM),
        fat_g=round(calories * FAT_CALORIE_SHARE / FAT_KCAL_PER_GRAM),
    )


def calculate_targets(
    *,
    sex: Sex,
    weight_kg: float,
    height_cm: float,
    age_years: int,
    activity_level: ActivityLevel,
    goal_type: GoalType,
    intensity: GoalIntensity = GoalIntensity.STANDARD,
) -> CalorieTargetResult:
    bmr = calculate_bmr(sex=sex, weight_kg=weight_kg, height_cm=height_cm, age_years=age_years)
    tdee = calculate_tdee(bmr=bmr, activity_level=activity_level)

    adjustment = INTENSITY_DAILY_KCAL_ADJUSTMENT[intensity]
    if goal_type == GoalType.LOSE_WEIGHT:
        raw_target = tdee - adjustment
    elif goal_type == GoalType.GAIN_WEIGHT:
        raw_target = tdee + adjustment
    else:
        raw_target = tdee

    target_calories = round(raw_target)
    warnings: list[str] = []
    is_safe = True
    safer_alternative: int | None = None

    weekly_rate_kg = adjustment * 7 / KCAL_PER_KG_BODYWEIGHT

    if goal_type != GoalType.MAINTAIN_WEIGHT and weekly_rate_kg > MAX_SAFE_WEEKLY_RATE_KG:
        is_safe = False
        warnings.append(
            "This rate of weight change is more aggressive than generally recommended. "
            "Consider a lighter intensity, and consult a qualified healthcare professional "
            "before pursuing rapid weight change."
        )

    if target_calories < MIN_SAFE_DAILY_CALORIES:
        is_safe = False
        warnings.append(
            f"A target of {target_calories} kcal/day is below the general minimum of "
            f"{MIN_SAFE_DAILY_CALORIES} kcal/day. Extreme calorie restriction is not "
            "supported — consult a qualified healthcare professional."
        )

    if not is_safe:
        safer_target = round(
            tdee - INTENSITY_DAILY_KCAL_ADJUSTMENT[GoalIntensity.LIGHT]
            if goal_type == GoalType.LOSE_WEIGHT
            else tdee + INTENSITY_DAILY_KCAL_ADJUSTMENT[GoalIntensity.LIGHT]
            if goal_type == GoalType.GAIN_WEIGHT
            else tdee
        )
        safer_alternative = max(safer_target, MIN_SAFE_DAILY_CALORIES)

    return CalorieTargetResult(
        bmr=round(bmr),
        tdee=round(tdee),
        target_calories=target_calories,
        macros=macros_for_calories(target_calories),
        is_safe=is_safe,
        warnings=warnings,
        safer_alternative_calories=safer_alternative,
    )
