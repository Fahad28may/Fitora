import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Text, TextInput, TouchableOpacity, View } from "react-native";

import { ApiError } from "../../src/api/client";
import type { WeightEntryOut } from "../../src/api/types";
import { weightApi } from "../../src/api/weight";
import { formStyles as s } from "../../src/ui/formStyles";
import { todayIso } from "../../src/utils/date";
import { screenStyles } from "./styles";

export default function ProgressScreen(): React.JSX.Element {
  const [entries, setEntries] = useState<WeightEntryOut[]>([]);
  const [weightKg, setWeightKg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    const data = await weightApi.list();
    setEntries(data);
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
              keyboardType="numeric"
              value={weightKg}
              onChangeText={setWeightKg}
            />
            <TouchableOpacity
              style={[s.button, { marginTop: 0 }, (!weightKg || isSubmitting) && s.buttonDisabled]}
              onPress={() => void handleLog()}
              disabled={!weightKg || isSubmitting}
            >
              {isSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Log</Text>}
            </TouchableOpacity>
          </View>

          {error ? <Text style={s.error}>{error}</Text> : null}
          {isLoading ? <ActivityIndicator /> : null}
          {!isLoading && entries.length === 0 ? (
            <Text style={screenStyles.body}>No weight entries yet.</Text>
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
          <TouchableOpacity onPress={() => void handleDelete(item.id)}>
            <Text style={[s.error, { fontSize: 13 }]}>Delete</Text>
          </TouchableOpacity>
        </View>
      )}
    />
  );
}
