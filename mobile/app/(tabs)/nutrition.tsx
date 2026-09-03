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
import { foodDiaryApi } from "../../src/api/foodDiary";
import { foodsApi } from "../../src/api/foods";
import type { FoodDiaryEntryOut, FoodOut, LogUnit, MealCategory } from "../../src/api/types";
import { formStyles as s } from "../../src/ui/formStyles";
import { todayIso } from "../../src/utils/date";
import { screenStyles } from "./styles";

const MEAL_CATEGORIES: MealCategory[] = ["breakfast", "lunch", "dinner", "snack"];

export default function NutritionScreen(): React.JSX.Element {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<FoodOut[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  const [selectedFood, setSelectedFood] = useState<FoodOut | null>(null);
  const [quantity, setQuantity] = useState("1");
  const [unit, setUnit] = useState<LogUnit>("serving");
  const [mealCategory, setMealCategory] = useState<MealCategory>("snack");
  const [logError, setLogError] = useState<string | null>(null);
  const [isLogging, setIsLogging] = useState(false);

  const [diaryEntries, setDiaryEntries] = useState<FoodDiaryEntryOut[]>([]);

  const loadDiary = useCallback(async () => {
    setDiaryEntries(await foodDiaryApi.listForDate(todayIso()));
  }, []);

  useEffect(() => {
    // Fetch-on-mount: setState happens after the awaited API call resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadDiary();
  }, [loadDiary]);

  async function handleSearch(): Promise<void> {
    if (query.trim().length < 2) {
      setSearchError("Enter at least 2 characters.");
      return;
    }
    setSearchError(null);
    setShowCreateForm(false);
    setIsSearching(true);
    try {
      setResults(await foodsApi.search(query.trim()));
      setHasSearched(true);
    } catch (err) {
      setSearchError(err instanceof ApiError ? err.message : "Search failed.");
    } finally {
      setIsSearching(false);
    }
  }

  function handleFoodCreated(food: FoodOut): void {
    setShowCreateForm(false);
    setSelectedFood(food);
  }

  async function handleLog(): Promise<void> {
    if (!selectedFood) return;
    setLogError(null);
    setIsLogging(true);
    try {
      await foodDiaryApi.create({
        food_id: selectedFood.id,
        logged_at: todayIso(),
        meal_category: mealCategory,
        quantity: Number(quantity),
        unit,
      });
      setSelectedFood(null);
      setQuantity("1");
      await loadDiary();
    } catch (err) {
      setLogError(err instanceof ApiError ? err.message : "Could not log this food.");
    } finally {
      setIsLogging(false);
    }
  }

  async function handleDeleteEntry(id: string): Promise<void> {
    await foodDiaryApi.remove(id);
    await loadDiary();
  }

  return (
    <FlatList
      contentContainerStyle={screenStyles.container}
      data={diaryEntries}
      keyExtractor={(item) => item.id}
      ListHeaderComponent={
        <View style={{ gap: 12, marginBottom: 8 }}>
          <Text style={screenStyles.title}>Nutrition</Text>

          <View style={{ flexDirection: "row", gap: 10 }}>
            <TextInput
              style={[s.input, { flex: 1 }]}
              placeholder="Search foods (e.g. egg)"
              value={query}
              onChangeText={setQuery}
              onSubmitEditing={() => void handleSearch()}
            />
            <TouchableOpacity style={[s.button, { marginTop: 0 }]} onPress={() => void handleSearch()}>
              {isSearching ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Go</Text>}
            </TouchableOpacity>
          </View>
          {searchError ? <Text style={s.error}>{searchError}</Text> : null}

          {results.map((food) => (
            <TouchableOpacity
              key={food.id}
              style={s.card}
              onPress={() => setSelectedFood(food)}
            >
              <Text style={screenStyles.cardTitle}>{food.name}</Text>
              <Text style={screenStyles.body}>
                {food.serving_description} — {food.calories_kcal} kcal
              </Text>
            </TouchableOpacity>
          ))}

          {hasSearched && !isSearching && results.length === 0 && !showCreateForm ? (
            <TouchableOpacity onPress={() => setShowCreateForm(true)}>
              <Text style={s.secondaryButtonText}>Can&apos;t find it? Create a custom food</Text>
            </TouchableOpacity>
          ) : null}

          {showCreateForm ? (
            <CreateFoodForm initialName={query} onCreated={handleFoodCreated} />
          ) : null}

          {selectedFood ? (
            <View style={[s.card, { gap: 10 }]}>
              <Text style={screenStyles.cardTitle}>Log {selectedFood.name}</Text>

              <View style={{ flexDirection: "row", gap: 10 }}>
                <TextInput
                  style={[s.input, { flex: 1 }]}
                  placeholder="Quantity"
                  keyboardType="numeric"
                  value={quantity}
                  onChangeText={setQuantity}
                />
                <View style={s.optionRow}>
                  {(["serving", "gram"] as LogUnit[]).map((u) => (
                    <TouchableOpacity
                      key={u}
                      style={[s.optionChip, unit === u && s.optionChipSelected]}
                      onPress={() => setUnit(u)}
                    >
                      <Text style={[s.optionChipText, unit === u && s.optionChipTextSelected]}>
                        {u}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              <View style={s.optionRow}>
                {MEAL_CATEGORIES.map((category) => (
                  <TouchableOpacity
                    key={category}
                    style={[s.optionChip, mealCategory === category && s.optionChipSelected]}
                    onPress={() => setMealCategory(category)}
                  >
                    <Text
                      style={[
                        s.optionChipText,
                        mealCategory === category && s.optionChipTextSelected,
                      ]}
                    >
                      {category}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {logError ? <Text style={s.error}>{logError}</Text> : null}

              <TouchableOpacity
                style={[s.button, (!quantity || isLogging) && s.buttonDisabled]}
                onPress={() => void handleLog()}
                disabled={!quantity || isLogging}
              >
                {isLogging ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Add to diary</Text>}
              </TouchableOpacity>
            </View>
          ) : null}

          <Text style={screenStyles.cardTitle}>Today</Text>
          {diaryEntries.length === 0 ? (
            <Text style={screenStyles.body}>Nothing logged yet today.</Text>
          ) : null}
        </View>
      }
      renderItem={({ item }) => (
        <View style={[screenStyles.card, { marginBottom: 10 }]}>
          <View style={screenStyles.row}>
            <Text style={screenStyles.cardTitle}>{item.food_name}</Text>
            <Text style={screenStyles.body}>{Math.round(item.calories_kcal)} kcal</Text>
          </View>
          <Text style={screenStyles.body}>
            {item.quantity} {item.unit} · {item.meal_category}
          </Text>
          <TouchableOpacity onPress={() => void handleDeleteEntry(item.id)}>
            <Text style={[s.error, { fontSize: 13 }]}>Delete</Text>
          </TouchableOpacity>
        </View>
      )}
    />
  );
}

function CreateFoodForm({
  initialName,
  onCreated,
}: {
  initialName: string;
  onCreated: (food: FoodOut) => void;
}): React.JSX.Element {
  const [name, setName] = useState(initialName);
  const [servingDescription, setServingDescription] = useState("");
  const [servingGrams, setServingGrams] = useState("");
  const [calories, setCalories] = useState("");
  const [protein, setProtein] = useState("");
  const [carbs, setCarbs] = useState("");
  const [fat, setFat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit =
    name.trim().length > 0 &&
    servingDescription.trim().length > 0 &&
    Number(servingGrams) > 0 &&
    Number(calories) >= 0 &&
    Number(protein) >= 0 &&
    Number(carbs) >= 0 &&
    Number(fat) >= 0;

  async function handleSubmit(): Promise<void> {
    setError(null);
    setIsSubmitting(true);
    try {
      const food = await foodsApi.create({
        name: name.trim(),
        serving_description: servingDescription.trim(),
        serving_grams: Number(servingGrams),
        calories_kcal: Number(calories),
        protein_g: Number(protein),
        carbs_g: Number(carbs),
        fat_g: Number(fat),
      });
      onCreated(food);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create this food.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={[s.card, { gap: 10 }]}>
      <Text style={screenStyles.cardTitle}>New custom food</Text>
      <TextInput style={s.input} placeholder="Name" value={name} onChangeText={setName} />
      <TextInput
        style={s.input}
        placeholder="Serving description (e.g. 1 cup)"
        value={servingDescription}
        onChangeText={setServingDescription}
      />
      <TextInput
        style={s.input}
        placeholder="Serving size (grams)"
        keyboardType="numeric"
        value={servingGrams}
        onChangeText={setServingGrams}
      />
      <TextInput
        style={s.input}
        placeholder="Calories (kcal) per serving"
        keyboardType="numeric"
        value={calories}
        onChangeText={setCalories}
      />
      <TextInput
        style={s.input}
        placeholder="Protein (g) per serving"
        keyboardType="numeric"
        value={protein}
        onChangeText={setProtein}
      />
      <TextInput
        style={s.input}
        placeholder="Carbs (g) per serving"
        keyboardType="numeric"
        value={carbs}
        onChangeText={setCarbs}
      />
      <TextInput
        style={s.input}
        placeholder="Fat (g) per serving"
        keyboardType="numeric"
        value={fat}
        onChangeText={setFat}
      />
      {error ? <Text style={s.error}>{error}</Text> : null}
      <TouchableOpacity
        style={[s.button, (!canSubmit || isSubmitting) && s.buttonDisabled]}
        onPress={() => void handleSubmit()}
        disabled={!canSubmit || isSubmitting}
      >
        {isSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Create food</Text>}
      </TouchableOpacity>
    </View>
  );
}
