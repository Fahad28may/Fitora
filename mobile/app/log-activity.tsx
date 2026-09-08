import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import {
  ACTIVITY_LIMITS,
  activityApi,
  type ActivityEntryOut,
  type ActivityType,
} from "../src/api/activity";
import { ApiError } from "../src/api/client";
import { outbox } from "../src/api/outbox";
import { formStyles as s } from "../src/ui/formStyles";
import { todayIso } from "../src/utils/date";
import { screenStyles } from "./(tabs)/styles";

const ACTIVITY_OPTIONS: { label: string; value: ActivityType }[] = [
  { label: "Walking", value: "walking" },
  { label: "Running", value: "running" },
  { label: "Cycling", value: "cycling" },
  { label: "Swimming", value: "swimming" },
  { label: "Strength", value: "strength" },
  { label: "Sport", value: "sport" },
  { label: "Other", value: "other" },
];

const SOURCE_LABEL: Record<string, string> = {
  manual: "Typed by you",
  apple_health: "From Apple Health",
  health_connect: "From Health Connect",
  wearable: "From a wearable",
};

/**
 * Parse an optional numeric field.
 *
 * Returns `undefined` for blank (the field wasn't filled in) and `null` for
 * unparseable, which the caller reports rather than silently dropping — a
 * typo'd distance quietly becoming "no distance" is the kind of thing a user
 * only discovers weeks later in a chart.
 */
function parseOptionalNumber(raw: string): number | undefined | null {
  const trimmed = raw.trim();
  if (trimmed === "") return undefined;
  const value = Number(trimmed);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

export default function LogActivityScreen(): React.JSX.Element {
  const [entries, setEntries] = useState<ActivityEntryOut[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [activityType, setActivityType] = useState<ActivityType>("walking");
  const [durationMin, setDurationMin] = useState("");
  const [distanceKm, setDistanceKm] = useState("");
  const [steps, setSteps] = useState("");
  const [caloriesBurned, setCaloriesBurned] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      setEntries(await activityApi.listForDate(todayIso()));
    } catch {
      // The log is secondary to the form; a read failure shouldn't block
      // logging something new.
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount: setState happens after the awaited API call resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function resetForm(): void {
    setDurationMin("");
    setDistanceKm("");
    setSteps("");
    setCaloriesBurned("");
  }

  async function handleLog(): Promise<void> {
    setError(null);
    setNotice(null);

    const duration = Number(durationMin.trim());
    if (!Number.isInteger(duration) || duration <= 0) {
      setError("Enter how many minutes it lasted.");
      return;
    }
    if (duration > ACTIVITY_LIMITS.maxDurationMin) {
      setError("That's longer than a day — check the minutes.");
      return;
    }

    const distance = parseOptionalNumber(distanceKm);
    const stepCount = parseOptionalNumber(steps);
    const burned = parseOptionalNumber(caloriesBurned);
    if (distance === null || stepCount === null || burned === null) {
      setError("Distance, steps and calories need to be numbers.");
      return;
    }

    setIsSubmitting(true);
    try {
      // Through the outbox, like water: a tap on a flaky connection is
      // queued with a stable idempotency key rather than logged twice.
      const queued = await outbox.send(
        "/api/v1/activity-entries",
        {
          logged_at: todayIso(),
          activity_type: activityType,
          duration_min: duration,
          distance_km: distance ?? null,
          steps: stepCount ?? null,
          calories_burned: burned ?? null,
        },
        `${duration} min of ${activityType}`
      );
      resetForm();
      // `send` returns null when the network was down and the write was
      // queued. Saying so beats a silent success the user later can't find.
      setNotice(
        queued === null
          ? "Saved on this device — it'll sync when you're back online."
          : null
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log that activity.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(entry: ActivityEntryOut): Promise<void> {
    setError(null);
    try {
      await activityApi.remove(entry.id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete that entry.");
    }
  }

  return (
    <ScrollView contentContainerStyle={s.container}>
      <Text style={s.title}>Log activity</Text>
      <Text style={s.subtitle}>
        Anything that isn&apos;t a tracked workout — a walk, a ride, a swim.
      </Text>

      <Text style={s.label}>Type</Text>
      <View style={s.optionRow}>
        {ACTIVITY_OPTIONS.map((option) => {
          const selected = option.value === activityType;
          return (
            <TouchableOpacity
              key={option.value}
              style={[s.optionChip, selected && s.optionChipSelected]}
              onPress={() => setActivityType(option.value)}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={option.label}
            >
              <Text style={[s.optionChipText, selected && s.optionChipTextSelected]}>
                {option.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <Text style={s.label}>Minutes</Text>
      <TextInput
        style={s.input}
        placeholder="30"
        keyboardType="numeric"
        value={durationMin}
        onChangeText={setDurationMin}
        accessibilityLabel="Minutes"
      />

      <Text style={s.label}>Distance in kilometres (optional)</Text>
      <TextInput
        style={s.input}
        placeholder="5.4"
        keyboardType="numeric"
        value={distanceKm}
        onChangeText={setDistanceKm}
        accessibilityLabel="Distance in kilometres"
      />

      <Text style={s.label}>Steps (optional)</Text>
      <TextInput
        style={s.input}
        placeholder="6100"
        keyboardType="numeric"
        value={steps}
        onChangeText={setSteps}
        accessibilityLabel="Steps"
      />

      <Text style={s.label}>Calories burned (optional)</Text>
      <TextInput
        style={s.input}
        placeholder="340"
        keyboardType="numeric"
        value={caloriesBurned}
        onChangeText={setCaloriesBurned}
        accessibilityLabel="Calories burned"
      />
      <Text style={s.helpText}>
        Your own estimate. Fitora doesn&apos;t calculate calorie burn, and doesn&apos;t
        subtract it from your target.
      </Text>

      <TouchableOpacity
        style={[s.button, isSubmitting && s.buttonDisabled]}
        disabled={isSubmitting}
        onPress={() => void handleLog()}
        accessibilityRole="button"
        accessibilityLabel="Log this activity"
      >
        {isSubmitting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={s.buttonText}>Log this activity</Text>
        )}
      </TouchableOpacity>

      {error ? <Text style={s.error}>{error}</Text> : null}
      {notice ? <Text style={s.helpText}>{notice}</Text> : null}

      <Text style={[screenStyles.cardTitle, { marginTop: 16 }]}>Today</Text>
      {isLoading ? (
        <ActivityIndicator />
      ) : entries.length === 0 ? (
        <Text style={s.helpText}>Nothing logged today.</Text>
      ) : (
        entries.map((entry) => (
          <View key={entry.id} style={[s.card, { gap: 4 }]}>
            <View style={s.row}>
              <Text style={screenStyles.body}>
                {entry.activity_type} · {entry.duration_min} min
              </Text>
              <TouchableOpacity
                onPress={() => void handleDelete(entry)}
                accessibilityRole="button"
                accessibilityLabel={`Delete ${entry.activity_type} entry`}
              >
                <Text style={[s.secondaryButtonText, { color: "#dc2626" }]}>Delete</Text>
              </TouchableOpacity>
            </View>
            {entry.distance_km !== null || entry.steps !== null ? (
              <Text style={s.helpText}>
                {[
                  entry.distance_km !== null ? `${entry.distance_km} km` : null,
                  entry.steps !== null ? `${entry.steps.toLocaleString()} steps` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </Text>
            ) : null}
            {/* Where a record came from is part of what it means. A step count
                a watch reported and one a user typed are different claims. */}
            <Text style={s.helpText}>{SOURCE_LABEL[entry.source] ?? entry.source}</Text>
          </View>
        ))
      )}

      <TouchableOpacity
        style={{ marginTop: 20 }}
        onPress={() => router.back()}
        accessibilityRole="button"
        accessibilityLabel="Back"
      >
        <Text style={s.secondaryButtonText}>Back</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
