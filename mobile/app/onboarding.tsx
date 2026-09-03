import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import { ApiError } from "../src/api/client";
import { goalsApi } from "../src/api/goals";
import { profileApi } from "../src/api/profile";
import type {
  ActivityLevel,
  GoalIntensity,
  GoalType,
  Sex,
  UnsafeGoalDetail,
} from "../src/api/types";
import { formStyles as s } from "../src/ui/formStyles";

const SEX_OPTIONS: { label: string; value: Sex }[] = [
  { label: "Female", value: "female" },
  { label: "Male", value: "male" },
];

const ACTIVITY_OPTIONS: { label: string; value: ActivityLevel }[] = [
  { label: "Sedentary", value: "sedentary" },
  { label: "Light", value: "light" },
  { label: "Moderate", value: "moderate" },
  { label: "Active", value: "active" },
  { label: "Very active", value: "very_active" },
];

const GOAL_TYPE_OPTIONS: { label: string; value: GoalType }[] = [
  { label: "Lose weight", value: "lose_weight" },
  { label: "Maintain", value: "maintain_weight" },
  { label: "Gain weight", value: "gain_weight" },
];

const INTENSITY_OPTIONS: { label: string; value: GoalIntensity }[] = [
  { label: "Light", value: "light" },
  { label: "Standard", value: "standard" },
  { label: "Aggressive", value: "aggressive" },
];

function Chips<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { label: string; value: T }[];
  value: T | null;
  onChange: (value: T) => void;
}): React.JSX.Element {
  return (
    <View style={s.optionRow}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <TouchableOpacity
            key={option.value}
            style={[s.optionChip, selected && s.optionChipSelected]}
            onPress={() => onChange(option.value)}
          >
            <Text style={[s.optionChipText, selected && s.optionChipTextSelected]}>
              {option.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

export default function OnboardingScreen(): React.JSX.Element {
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [sex, setSex] = useState<Sex | null>(null);
  const [heightCm, setHeightCm] = useState("");
  const [activityLevel, setActivityLevel] = useState<ActivityLevel | null>(null);
  const [goalType, setGoalType] = useState<GoalType | null>(null);
  const [intensity, setIntensity] = useState<GoalIntensity>("standard");
  const [currentWeightKg, setCurrentWeightKg] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [unsafeGoal, setUnsafeGoal] = useState<UnsafeGoalDetail | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit =
    /^\d{4}-\d{2}-\d{2}$/.test(dateOfBirth) &&
    sex !== null &&
    Number(heightCm) > 0 &&
    activityLevel !== null &&
    goalType !== null &&
    Number(currentWeightKg) > 0;

  async function submit(acknowledgeRisk: boolean): Promise<void> {
    if (!sex || !activityLevel || !goalType) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await profileApi.update({
        date_of_birth: dateOfBirth,
        sex,
        height_cm: Number(heightCm),
        activity_level: activityLevel,
        unit_system: "metric",
      });
      await goalsApi.create({
        goal_type: goalType,
        intensity,
        current_weight_kg: Number(currentWeightKg),
        acknowledge_risk: acknowledgeRisk,
      });
      setUnsafeGoal(null);
      router.replace("/(tabs)");
    } catch (err) {
      const detail = err instanceof ApiError && err.status === 422 ? asUnsafeGoalDetail(err.detail) : null;
      if (detail) {
        setUnsafeGoal(detail);
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={s.container}>
      <Text style={s.title}>Set up your profile</Text>
      <Text style={s.subtitle}>
        This is used only to calculate your calorie and macro estimates — see the health
        disclaimer for what these numbers do and don&apos;t mean.
      </Text>

      <Text style={s.label}>Date of birth (YYYY-MM-DD)</Text>
      <TextInput
        style={s.input}
        placeholder="1995-06-15"
        value={dateOfBirth}
        onChangeText={setDateOfBirth}
      />

      <Text style={s.label}>Sex</Text>
      <Chips options={SEX_OPTIONS} value={sex} onChange={setSex} />

      <Text style={s.label}>Height (cm)</Text>
      <TextInput
        style={s.input}
        placeholder="170"
        keyboardType="numeric"
        value={heightCm}
        onChangeText={setHeightCm}
      />

      <Text style={s.label}>Activity level</Text>
      <Chips options={ACTIVITY_OPTIONS} value={activityLevel} onChange={setActivityLevel} />

      <Text style={s.label}>Goal</Text>
      <Chips options={GOAL_TYPE_OPTIONS} value={goalType} onChange={setGoalType} />

      <Text style={s.label}>Intensity</Text>
      <Chips options={INTENSITY_OPTIONS} value={intensity} onChange={setIntensity} />

      <Text style={s.label}>Current weight (kg)</Text>
      <TextInput
        style={s.input}
        placeholder="70"
        keyboardType="numeric"
        value={currentWeightKg}
        onChangeText={setCurrentWeightKg}
      />

      {error ? <Text style={s.error}>{error}</Text> : null}

      {unsafeGoal ? (
        <View style={{ gap: 8 }}>
          {unsafeGoal.warnings.map((warning) => (
            <Text key={warning} style={s.warning}>
              {warning}
            </Text>
          ))}
          {unsafeGoal.safer_alternative_calories ? (
            <Text style={s.subtitle}>
              A lighter intensity would target about {unsafeGoal.safer_alternative_calories}{" "}
              kcal/day instead.
            </Text>
          ) : null}
          <TouchableOpacity
            style={s.secondaryButton}
            onPress={() => void submit(true)}
            disabled={isSubmitting}
          >
            <Text style={s.secondaryButtonText}>I understand — continue anyway</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <TouchableOpacity
          style={[s.button, (!canSubmit || isSubmitting) && s.buttonDisabled]}
          onPress={() => void submit(false)}
          disabled={!canSubmit || isSubmitting}
        >
          {isSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Save</Text>}
        </TouchableOpacity>
      )}
    </ScrollView>
  );
}

function asUnsafeGoalDetail(detail: unknown): UnsafeGoalDetail | null {
  if (detail && typeof detail === "object" && "warnings" in detail) {
    return detail as UnsafeGoalDetail;
  }
  return null;
}
