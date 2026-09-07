import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Text, TextInput, TouchableOpacity, View } from "react-native";

import { ApiError } from "../../src/api/client";
import { historyApi, type HistoryOut } from "../../src/api/history";
import type { BodyMeasurementOut } from "../../src/api/measurements";
import { measurementsApi } from "../../src/api/measurements";
import type { WeightEntryOut } from "../../src/api/types";
import { weightApi } from "../../src/api/weight";
import { formStyles as s } from "../../src/ui/formStyles";
import { TrendChart, type TrendPoint } from "../../src/ui/TrendChart";
import { todayIso } from "../../src/utils/date";
import { screenStyles } from "./styles";

// API lists are newest-first; charts read oldest-to-newest. Labels are MM-DD.
function toChronologicalPoints<T>(
  rows: T[],
  getDate: (row: T) => string,
  getValue: (row: T) => number | null,
): TrendPoint[] {
  return rows
    .filter((row) => getValue(row) !== null)
    .map((row) => ({ label: getDate(row).slice(5), value: getValue(row) as number }))
    .reverse();
}

export default function ProgressScreen(): React.JSX.Element {
  const [entries, setEntries] = useState<WeightEntryOut[]>([]);
  const [weightKg, setWeightKg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const [measurements, setMeasurements] = useState<BodyMeasurementOut[]>([]);
  const [history, setHistory] = useState<HistoryOut | null>(null);

  const load = useCallback(async () => {
    const [weightData, measurementData, historyData] = await Promise.all([
      weightApi.list(),
      measurementsApi.list(),
      // Charts are secondary; a failure there must not blank the log below,
      // which is the screen's actual job.
      historyApi.get().catch(() => null),
    ]);
    setHistory(historyData);
    setEntries(weightData);
    setMeasurements(measurementData);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    // Fetch-on-mount: setState happens after the awaited API call resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function handleLog(): Promise<void> {
    setError(null);
    setIsSubmitting(true);
    try {
      await weightApi.create({ logged_at: todayIso(), weight_kg: Number(weightKg) });
      setWeightKg("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log weight.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(id: string): Promise<void> {
    await weightApi.remove(id);
    await load();
  }

  async function handleDeleteMeasurement(id: string): Promise<void> {
    await measurementsApi.remove(id);
    await load();
  }

  return (
    <FlatList
      contentContainerStyle={screenStyles.container}
      ListHeaderComponent={
        <View style={{ gap: 12, marginBottom: 8 }}>
          <Text style={screenStyles.title}>Progress</Text>

          <View style={{ flexDirection: "row", gap: 10 }}>
            <TextInput
              style={[s.input, { flex: 1 }]}
              placeholder="Weight today (kg)"
          accessibilityLabel="Weight today (kg)"
              keyboardType="numeric"
              value={weightKg}
              onChangeText={setWeightKg}
            />
            <TouchableOpacity
              style={[s.button, { marginTop: 0 }, (!weightKg || isSubmitting) && s.buttonDisabled]}
              onPress={() => void handleLog()}
              disabled={!weightKg || isSubmitting}
              accessibilityRole="button"
              accessibilityLabel="Log today's weight"
            >
              {isSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Log</Text>}
            </TouchableOpacity>
          </View>

          {error ? <Text style={s.error}>{error}</Text> : null}
          {isLoading ? <ActivityIndicator /> : null}
          {!isLoading && entries.length === 0 ? (
            <Text style={screenStyles.body}>No weight entries yet.</Text>
          ) : null}

          <TrendChart
            title="Weight trend"
            unit="kg"
            points={toChronologicalPoints(
              entries,
              (e) => e.logged_at,
              (e) => e.weight_kg,
            )}
          />

          {/* History points arrive oldest-first already, and include days
              with nothing logged so a gap reads as a gap. */}
          {history !== null ? (
            <>
              <TrendChart
                title="Calories"
                unit=" kcal"
                points={history.points.map((p) => ({
                  label: p.date.slice(5),
                  value: p.calories_kcal,
                }))}
              />
              <TrendChart
                title="Protein"
                unit="g"
                points={history.points.map((p) => ({
                  label: p.date.slice(5),
                  value: p.protein_g,
                }))}
              />
              <TrendChart
                title="Activity"
                unit=" min"
                points={history.points.map((p) => ({
                  label: p.date.slice(5),
                  value: p.activity_minutes,
                }))}
              />
            </>
          ) : null}
        </View>
      }
      data={entries}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <View style={[screenStyles.card, { marginBottom: 10 }]}>
          <View style={screenStyles.row}>
            <Text style={screenStyles.body}>{item.logged_at}</Text>
            <Text style={screenStyles.cardTitle}>{item.weight_kg} kg</Text>
          </View>
          <TouchableOpacity
            onPress={() => void handleDelete(item.id)}
            accessibilityRole="button"
            accessibilityLabel={`Delete weight entry from ${item.logged_at}`}
          >
            <Text style={[s.error, { fontSize: 13 }]}>Delete</Text>
          </TouchableOpacity>
        </View>
      )}
      ListFooterComponent={
        <MeasurementsSection
          measurements={measurements}
          onCreated={load}
          onDelete={(id) => void handleDeleteMeasurement(id)}
        />
      }
    />
  );
}

function MeasurementsSection({
  measurements,
  onCreated,
  onDelete,
}: {
  measurements: BodyMeasurementOut[];
  onCreated: () => Promise<void>;
  onDelete: (id: string) => void;
}): React.JSX.Element {
  const [waist, setWaist] = useState("");
  const [chest, setChest] = useState("");
  const [arm, setArm] = useState("");
  const [leg, setLeg] = useState("");
  const [hip, setHip] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const toNumberOrNull = (value: string): number | null =>
    value.trim() === "" ? null : Number(value);

  const canSubmit = [waist, chest, arm, leg, hip].some((v) => v.trim() !== "");

  async function handleSubmit(): Promise<void> {
    setError(null);
    setIsSubmitting(true);
    try {
      await measurementsApi.create({
        logged_at: todayIso(),
        waist_cm: toNumberOrNull(waist),
        chest_cm: toNumberOrNull(chest),
        arm_cm: toNumberOrNull(arm),
        leg_cm: toNumberOrNull(leg),
        hip_cm: toNumberOrNull(hip),
      });
      setWaist("");
      setChest("");
      setArm("");
      setLeg("");
      setHip("");
      await onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log measurements.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={{ gap: 12, marginTop: 20 }}>
      <Text style={screenStyles.cardTitle}>Measurements</Text>

      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
        <TextInput
          style={[s.input, { flex: 1, minWidth: 100 }]}
          placeholder="Waist (cm)"
          accessibilityLabel="Waist (cm)"
          keyboardType="numeric"
          value={waist}
          onChangeText={setWaist}
        />
        <TextInput
          style={[s.input, { flex: 1, minWidth: 100 }]}
          placeholder="Chest (cm)"
          accessibilityLabel="Chest (cm)"
          keyboardType="numeric"
          value={chest}
          onChangeText={setChest}
        />
        <TextInput
          style={[s.input, { flex: 1, minWidth: 100 }]}
          placeholder="Arm (cm)"
          accessibilityLabel="Arm (cm)"
          keyboardType="numeric"
          value={arm}
          onChangeText={setArm}
        />
        <TextInput
          style={[s.input, { flex: 1, minWidth: 100 }]}
          placeholder="Leg (cm)"
          accessibilityLabel="Leg (cm)"
          keyboardType="numeric"
          value={leg}
          onChangeText={setLeg}
        />
        <TextInput
          style={[s.input, { flex: 1, minWidth: 100 }]}
          placeholder="Hip (cm)"
          accessibilityLabel="Hip (cm)"
          keyboardType="numeric"
          value={hip}
          onChangeText={setHip}
        />
      </View>

      {error ? <Text style={s.error}>{error}</Text> : null}

      <TouchableOpacity
        style={[s.button, (!canSubmit || isSubmitting) && s.buttonDisabled]}
        onPress={() => void handleSubmit()}
        disabled={!canSubmit || isSubmitting}
        accessibilityRole="button"
        accessibilityLabel="Save measurements"
      >
        {isSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Log measurements</Text>}
      </TouchableOpacity>

      <TrendChart
        title="Waist trend"
        unit="cm"
        points={toChronologicalPoints(
          measurements,
          (m) => m.logged_at,
          (m) => m.waist_cm,
        )}
      />

      {measurements.length === 0 ? (
        <Text style={screenStyles.body}>No measurements logged yet.</Text>
      ) : (
        measurements.map((m) => (
          <View key={m.id} style={[screenStyles.card, { marginBottom: 10 }]}>
            <Text style={screenStyles.body}>{m.logged_at}</Text>
            <Text style={screenStyles.body}>
              {[
                m.waist_cm !== null ? `Waist ${m.waist_cm}cm` : null,
                m.chest_cm !== null ? `Chest ${m.chest_cm}cm` : null,
                m.arm_cm !== null ? `Arm ${m.arm_cm}cm` : null,
                m.leg_cm !== null ? `Leg ${m.leg_cm}cm` : null,
                m.hip_cm !== null ? `Hip ${m.hip_cm}cm` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </Text>
            <TouchableOpacity
              onPress={() => onDelete(m.id)}
              accessibilityRole="button"
              accessibilityLabel={`Delete measurements from ${m.logged_at}`}
            >
              <Text style={[s.error, { fontSize: 13 }]}>Delete</Text>
            </TouchableOpacity>
          </View>
        ))
      )}
    </View>
  );
}
