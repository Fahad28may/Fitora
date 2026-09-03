import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { ApiError } from "../../src/api/client";
import { exercisesApi, type ExerciseOut } from "../../src/api/exercises";
import { workoutSessionsApi, type WorkoutSessionOut } from "../../src/api/workouts";
import { formStyles as s } from "../../src/ui/formStyles";
import { screenStyles } from "./styles";

interface DraftSet {
  key: string;
  exerciseId: string;
  exerciseName: string;
  reps: string;
  weightKg: string;
}

export default function WorkoutScreen(): React.JSX.Element {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ExerciseOut[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [draftSets, setDraftSets] = useState<DraftSet[]>([]);
  const [logError, setLogError] = useState<string | null>(null);
  const [isLogging, setIsLogging] = useState(false);

  const [sessions, setSessions] = useState<WorkoutSessionOut[]>([]);

  const loadSessions = useCallback(async () => {
    setSessions(await workoutSessionsApi.list());
  }, []);

  useEffect(() => {
    // Fetch-on-mount: setState happens after the awaited API call resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadSessions();
  }, [loadSessions]);

  async function handleSearch(): Promise<void> {
    if (query.trim().length < 2) {
      setSearchError("Enter at least 2 characters.");
      return;
    }
    setSearchError(null);
    setIsSearching(true);
    try {
      setResults(await exercisesApi.search(query.trim()));
    } catch (err) {
      setSearchError(err instanceof ApiError ? err.message : "Search failed.");
    } finally {
      setIsSearching(false);
    }
  }

  function addExercise(exercise: ExerciseOut): void {
    setDraftSets((prev) => [
      ...prev,
      {
        key: `${exercise.id}-${Date.now()}`,
        exerciseId: exercise.id,
        exerciseName: exercise.name,
        reps: "",
        weightKg: "",
      },
    ]);
  }

  function updateDraftSet(key: string, field: "reps" | "weightKg", value: string): void {
    setDraftSets((prev) => prev.map((d) => (d.key === key ? { ...d, [field]: value } : d)));
  }

  function removeDraftSet(key: string): void {
    setDraftSets((prev) => prev.filter((d) => d.key !== key));
  }

  async function handleLogSession(): Promise<void> {
    if (draftSets.length === 0) return;
    setLogError(null);
    setIsLogging(true);
    try {
      const now = new Date().toISOString();
      await workoutSessionsApi.log({
        started_at: now,
        ended_at: now,
        sets: draftSets.map((d, index) => ({
          exercise_id: d.exerciseId,
          set_number: index + 1,
          reps: d.reps ? Number(d.reps) : null,
          weight_kg: d.weightKg ? Number(d.weightKg) : null,
        })),
      });
      setDraftSets([]);
      setResults([]);
      setQuery("");
      await loadSessions();
    } catch (err) {
      setLogError(err instanceof ApiError ? err.message : "Could not log this session.");
    } finally {
      setIsLogging(false);
    }
  }

  async function handleDeleteSession(id: string): Promise<void> {
    await workoutSessionsApi.remove(id);
    await loadSessions();
  }

  return (
    <FlatList
      contentContainerStyle={screenStyles.container}
      data={sessions}
      keyExtractor={(item) => item.id}
      ListHeaderComponent={
        <View style={{ gap: 12, marginBottom: 8 }}>
          <Text style={screenStyles.title}>Workout</Text>

          <View style={{ flexDirection: "row", gap: 10 }}>
            <TextInput
              style={[s.input, { flex: 1 }]}
              placeholder="Search exercises (e.g. squat)"
              value={query}
              onChangeText={setQuery}
              onSubmitEditing={() => void handleSearch()}
            />
            <TouchableOpacity style={[s.button, { marginTop: 0 }]} onPress={() => void handleSearch()}>
              {isSearching ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Go</Text>}
            </TouchableOpacity>
          </View>
          {searchError ? <Text style={s.error}>{searchError}</Text> : null}

          {results.map((exercise) => (
            <TouchableOpacity
              key={exercise.id}
              style={s.card}
              onPress={() => addExercise(exercise)}
            >
              <Text style={screenStyles.cardTitle}>{exercise.name}</Text>
              <Text style={screenStyles.body}>
                {exercise.muscle_groups.join(", ")} · {exercise.difficulty}
              </Text>
            </TouchableOpacity>
          ))}

          {draftSets.length > 0 ? (
            <View style={[s.card, { gap: 10 }]}>
              <Text style={screenStyles.cardTitle}>This session</Text>
              {draftSets.map((d) => (
                <View key={d.key} style={{ gap: 6 }}>
                  <View style={screenStyles.row}>
                    <Text style={screenStyles.body}>{d.exerciseName}</Text>
                    <TouchableOpacity onPress={() => removeDraftSet(d.key)}>
                      <Text style={[s.error, { fontSize: 13 }]}>Remove</Text>
                    </TouchableOpacity>
                  </View>
                  <View style={{ flexDirection: "row", gap: 10 }}>
                    <TextInput
                      style={[s.input, { flex: 1 }]}
                      placeholder="Reps"
                      keyboardType="numeric"
                      value={d.reps}
                      onChangeText={(v) => updateDraftSet(d.key, "reps", v)}
                    />
                    <TextInput
                      style={[s.input, { flex: 1 }]}
                      placeholder="Weight (kg)"
                      keyboardType="numeric"
                      value={d.weightKg}
                      onChangeText={(v) => updateDraftSet(d.key, "weightKg", v)}
                    />
                  </View>
                </View>
              ))}

              {logError ? <Text style={s.error}>{logError}</Text> : null}

              <TouchableOpacity
                style={[s.button, isLogging && s.buttonDisabled]}
                onPress={() => void handleLogSession()}
                disabled={isLogging}
              >
                {isLogging ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={s.buttonText}>Log session</Text>
                )}
              </TouchableOpacity>
            </View>
          ) : null}

          <Text style={screenStyles.cardTitle}>Recent sessions</Text>
          {sessions.length === 0 ? (
            <Text style={screenStyles.body}>No sessions logged yet.</Text>
          ) : null}
        </View>
      }
      renderItem={({ item }) => (
        <View style={[screenStyles.card, { marginBottom: 10 }]}>
          <Text style={screenStyles.body}>{new Date(item.started_at).toLocaleDateString()}</Text>
          <Text style={screenStyles.cardTitle}>
            {[...new Set(item.sets.map((s2) => s2.exercise_name))].join(", ")}
          </Text>
          <Text style={screenStyles.body}>{item.sets.length} sets logged</Text>
          <TouchableOpacity onPress={() => void handleDeleteSession(item.id)}>
            <Text style={[s.error, { fontSize: 13 }]}>Delete</Text>
          </TouchableOpacity>
        </View>
      )}
    />
  );
}
