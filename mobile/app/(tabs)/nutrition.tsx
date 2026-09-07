import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { aiApi, type ParsedFoodItemOut } from "../../src/api/ai";
import { ApiError } from "../../src/api/client";
import { foodDiaryApi } from "../../src/api/foodDiary";
import { foodsApi } from "../../src/api/foods";
import { mealsApi, type MealOut } from "../../src/api/meals";
import type {
  FoodDiaryEntryOut,
  FoodOut,
  LogSource,
  LogUnit,
  MealCategory,
} from "../../src/api/types";
import { BarcodeScanner } from "../../src/ui/BarcodeScanner";
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
  // Provenance of the current selection, recorded on the diary entry so the
  // diary can tell a scanned food from a searched or AI-parsed one.
  const [logSource, setLogSource] = useState<LogSource>("search");
  const [quantity, setQuantity] = useState("1");
  const [unit, setUnit] = useState<LogUnit>("serving");
  const [mealCategory, setMealCategory] = useState<MealCategory>("snack");
  const [logError, setLogError] = useState<string | null>(null);
  const [isLogging, setIsLogging] = useState(false);

  const [diaryEntries, setDiaryEntries] = useState<FoodDiaryEntryOut[]>([]);

  const [meals, setMeals] = useState<MealOut[]>([]);
  const [mealError, setMealError] = useState<string | null>(null);
  const [savingMealFor, setSavingMealFor] = useState<MealCategory | null>(null);
  const [newMealName, setNewMealName] = useState("");

  const [showScanner, setShowScanner] = useState(false);
  const [isLookingUpBarcode, setIsLookingUpBarcode] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  const [showNLInput, setShowNLInput] = useState(false);
  const [nlText, setNlText] = useState("");
  const [nlResults, setNlResults] = useState<ParsedFoodItemOut[]>([]);
  const [nlError, setNlError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);

  const loadDiary = useCallback(async () => {
    const [entries, savedMeals] = await Promise.all([
      foodDiaryApi.listForDate(todayIso()),
      // Saved meals are a convenience; a failure here must not blank the
      // diary, which is the screen's actual job.
      mealsApi.list().catch(() => [] as MealOut[]),
    ]);
    setDiaryEntries(entries);
    setMeals(savedMeals);
  }, []);

  async function handleLogMeal(meal: MealOut, category: MealCategory): Promise<void> {
    setMealError(null);
    try {
      await mealsApi.log(meal.id, todayIso(), category);
      await loadDiary();
    } catch (err) {
      setMealError(err instanceof ApiError ? err.message : "Could not log that meal.");
    }
  }

  async function handleSaveCategoryAsMeal(category: MealCategory): Promise<void> {
    const entries = diaryEntries.filter((e) => e.meal_category === category);
    if (entries.length === 0) {
      setMealError(`Nothing logged as ${category} today to save.`);
      return;
    }
    setMealError(null);
    try {
      await mealsApi.create(
        newMealName.trim() || `My ${category}`,
        entries.map((e) => ({ food_id: e.food_id, quantity: e.quantity, unit: e.unit })),
      );
      setSavingMealFor(null);
      setNewMealName("");
      await loadDiary();
    } catch (err) {
      setMealError(err instanceof ApiError ? err.message : "Could not save that meal.");
    }
  }

  async function handleDeleteMeal(mealId: string): Promise<void> {
    await mealsApi.remove(mealId);
    await loadDiary();
  }

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
    setLogSource("manual");
  }

  async function handleBarcodeScanned(barcode: string): Promise<void> {
    setScanError(null);
    setIsLookingUpBarcode(true);
    try {
      const food = await foodsApi.lookupBarcode(barcode);
      setSelectedFood(food);
      setLogSource("barcode");
      setQuantity("1");
      setUnit("serving");
      setShowScanner(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setScanError(
          "Barcode lookup isn't configured on this server — search for the food by name instead.",
        );
      } else if (err instanceof ApiError && err.status === 404) {
        setScanError("That product isn't in the food database. You can add it as a custom food.");
      } else if (err instanceof ApiError && err.status === 422) {
        setScanError(
          "That product's nutrition data looked wrong, so it wasn't imported. Add it manually from the label.",
        );
      } else {
        setScanError(err instanceof ApiError ? err.message : "Barcode lookup failed.");
      }
    } finally {
      setIsLookingUpBarcode(false);
    }
  }

  async function handleParse(): Promise<void> {
    if (!nlText.trim()) return;
    setNlError(null);
    setIsParsing(true);
    try {
      const response = await aiApi.parseFood(nlText.trim());
      setNlResults(response.items);
      if (response.items.length === 0) {
        setNlError("Couldn't identify any foods in that — try describing it differently.");
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setNlError("AI food parsing isn't configured on this server — search or log manually instead.");
      } else {
        setNlError(err instanceof ApiError ? err.message : "Could not parse that.");
      }
    } finally {
      setIsParsing(false);
    }
  }

  function handleSelectParsedMatch(item: ParsedFoodItemOut, food: FoodOut): void {
    setSelectedFood(food);
    setLogSource("natural_language");
    setQuantity(String(item.quantity));
    setUnit("serving");
    setShowNLInput(false);
    setNlText("");
    setNlResults([]);
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
        source: logSource,
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

          {meals.length > 0 ? (
            <View style={[s.card, { gap: 10 }]}>
              <Text style={screenStyles.cardTitle}>My meals</Text>
              {meals.map((meal) => (
                <View key={meal.id} style={{ gap: 6 }}>
                  <Text style={screenStyles.body}>
                    {meal.name} — {meal.items.length}{" "}
                    {meal.items.length === 1 ? "item" : "items"},{" "}
                    {meal.total_calories_kcal} kcal
                  </Text>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                    {MEAL_CATEGORIES.map((category) => (
                      <TouchableOpacity
                        key={category}
                        style={s.optionChip}
                        onPress={() => void handleLogMeal(meal, category)}
                        accessibilityRole="button"
                        accessibilityLabel={`Log ${meal.name} as ${category}`}
                      >
                        <Text style={s.optionChipText}>Log as {category}</Text>
                      </TouchableOpacity>
                    ))}
                    <TouchableOpacity
                      onPress={() => void handleDeleteMeal(meal.id)}
                      accessibilityRole="button"
                      accessibilityLabel={`Delete saved meal ${meal.name}`}
                    >
                      <Text style={[s.secondaryButtonText, { color: "#dc2626" }]}>
                        Delete
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </View>
          ) : null}

          {/* Building a meal from what's already logged is far less work than
              re-picking every food in a separate builder screen. */}
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {MEAL_CATEGORIES.map((category) => (
              <TouchableOpacity
                key={category}
                style={s.optionChip}
                onPress={() => {
                  setMealError(null);
                  setSavingMealFor((c) => (c === category ? null : category));
                }}
                accessibilityRole="button"
                accessibilityLabel={`Save today's ${category} as a reusable meal`}
              >
                <Text style={s.optionChipText}>Save {category} as meal</Text>
              </TouchableOpacity>
            ))}
          </View>

          {savingMealFor !== null ? (
            <View style={{ flexDirection: "row", gap: 10 }}>
              <TextInput
                style={[s.input, { flex: 1 }]}
                placeholder={`Name (default: My ${savingMealFor})`}
                value={newMealName}
                onChangeText={setNewMealName}
                accessibilityLabel="Name for the saved meal"
              />
              <TouchableOpacity
                style={[s.button, { marginTop: 0 }]}
                onPress={() => void handleSaveCategoryAsMeal(savingMealFor)}
                accessibilityRole="button"
              >
                <Text style={s.buttonText}>Save</Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {mealError ? <Text style={s.error}>{mealError}</Text> : null}

          <TouchableOpacity
            onPress={() => {
              setScanError(null);
              setShowScanner((v) => !v);
              setShowNLInput(false);
            }}
          >
            <Text style={s.secondaryButtonText}>
              {showScanner ? "Close scanner" : "Scan a barcode"}
            </Text>
          </TouchableOpacity>

          {showScanner ? (
            <BarcodeScanner
              onScanned={(barcode) => void handleBarcodeScanned(barcode)}
              onCancel={() => setShowScanner(false)}
              isBusy={isLookingUpBarcode}
            />
          ) : null}
          {/* Outside the scanner block: a failed lookup closes nothing, and a
              503 needs to stay readable after the user closes the camera. */}
          {scanError ? <Text style={s.error}>{scanError}</Text> : null}

          <TouchableOpacity onPress={() => setShowNLInput((v) => !v)}>
            <Text style={s.secondaryButtonText}>
              {showNLInput ? "Search instead" : "Describe what you ate instead"}
            </Text>
          </TouchableOpacity>

          {showNLInput ? (
            <View style={{ gap: 10 }}>
              <View style={{ flexDirection: "row", gap: 10 }}>
                <TextInput
                  style={[s.input, { flex: 1 }]}
                  placeholder="e.g. two eggs and a cup of chai"
                  value={nlText}
                  onChangeText={setNlText}
                  onSubmitEditing={() => void handleParse()}
                />
                <TouchableOpacity
                  style={[s.button, { marginTop: 0 }]}
                  onPress={() => void handleParse()}
                >
                  {isParsing ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={s.buttonText}>Parse</Text>
                  )}
                </TouchableOpacity>
              </View>
              {nlError ? <Text style={s.error}>{nlError}</Text> : null}

              {nlResults.map((item) => (
                <View key={`${item.name}-${item.quantity}`} style={s.card}>
                  <Text style={screenStyles.cardTitle}>
                    {item.quantity} {item.unit} {item.name}
                  </Text>
                  {item.matches.length === 0 ? (
                    <Text style={screenStyles.body}>No matching food found — log manually.</Text>
                  ) : (
                    item.matches.map((food) => (
                      <TouchableOpacity
                        key={food.id}
                        onPress={() => handleSelectParsedMatch(item, food)}
                        style={{ paddingVertical: 4 }}
                      >
                        <Text style={screenStyles.body}>
                          → {food.name} ({food.serving_description}, {food.calories_kcal} kcal)
                        </Text>
                      </TouchableOpacity>
                    ))
                  )}
                </View>
              ))}
            </View>
          ) : null}

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
              onPress={() => {
                setSelectedFood(food);
                setLogSource("search");
              }}
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
              {selectedFood.source === "external_db" ? (
                <Text style={s.warning}>
                  These numbers come from Open Food Facts, a crowd-sourced database. Worth a
                  glance against the label before you log it.
                </Text>
              ) : null}

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
