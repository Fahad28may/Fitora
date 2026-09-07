import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import { dashboardApi } from "../../src/api/dashboard";
import type { Recommendation, RecommendationPriority } from "../../src/api/recommendations";
import { recommendationsApi } from "../../src/api/recommendations";
import type { DashboardOut } from "../../src/api/types";
import { waterApi } from "../../src/api/water";
import { useAuth } from "../../src/auth/AuthContext";
import { todayIso } from "../../src/utils/date";
import { screenStyles } from "./styles";

const QUICK_ADD_WATER_ML = [250, 500];

const PRIORITY_COLOR: Record<RecommendationPriority, string> = {
  warning: "#dc2626",
  suggestion: "#2563eb",
  info: "#059669",
};

export default function HomeScreen(): React.JSX.Element {
  const { user, logout } = useAuth();
  const [dashboard, setDashboard] = useState<DashboardOut | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      // Recommendations are advisory — a failure there must not blank the
      // dashboard, so they're fetched independently and tolerate errors.
      const [data, recs] = await Promise.all([
        dashboardApi.get(),
        recommendationsApi.get().catch(() => null),
      ]);
      setDashboard(data);
      setRecommendations(recs?.recommendations ?? []);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAddWater(amountMl: number): Promise<void> {
    await waterApi.create(todayIso(), amountMl);
    await load();
  }

  if (isLoading) {
    return (
      <View style={[screenStyles.container, { flex: 1, justifyContent: "center" }]}>
        <ActivityIndicator />
      </View>
    );
  }

  const needsSetup = dashboard ? !dashboard.has_profile || !dashboard.has_active_goal : false;

  return (
    <ScrollView
      contentContainerStyle={screenStyles.container}
      refreshControl={
        <RefreshControl
          refreshing={isRefreshing}
          onRefresh={() => {
            setIsRefreshing(true);
            void load();
          }}
        />
      }
    >
      <Text style={screenStyles.title}>How am I doing today?</Text>

      {needsSetup ? (
        <Pressable
          style={screenStyles.setupCard}
          onPress={() => router.push("/onboarding")}
        >
          <Text style={screenStyles.setupCardTitle}>Finish setting up</Text>
          <Text style={screenStyles.setupCardBody}>
            Add your profile and goal to see calorie and macro targets here.
          </Text>
        </Pressable>
      ) : dashboard ? (
        <>
          <View style={screenStyles.statRow}>
            <View style={screenStyles.statBox}>
              <Text style={screenStyles.statValue}>{Math.round(dashboard.calories.consumed)}</Text>
              <Text style={screenStyles.statLabel}>Consumed</Text>
            </View>
            <View style={screenStyles.statBox}>
              <Text style={screenStyles.statValue}>
                {dashboard.calories.remaining !== null
                  ? Math.round(dashboard.calories.remaining)
                  : "—"}
              </Text>
              <Text style={screenStyles.statLabel}>Remaining</Text>
            </View>
            <View style={screenStyles.statBox}>
              <Text style={screenStyles.statValue}>{dashboard.calories.target ?? "—"}</Text>
              <Text style={screenStyles.statLabel}>Target</Text>
            </View>
          </View>

          <View style={screenStyles.card}>
            <Text style={screenStyles.cardTitle}>Macros</Text>
            <MacroRow label="Protein" value={dashboard.protein} unit="g" />
            <MacroRow label="Carbs" value={dashboard.carbs} unit="g" />
            <MacroRow label="Fat" value={dashboard.fat} unit="g" />
          </View>

          <View style={screenStyles.card}>
            <Text style={screenStyles.cardTitle}>Water</Text>
            <Text style={screenStyles.body}>
              {dashboard.water.consumed_ml} ml
              {dashboard.water.target_ml !== null ? ` / ${dashboard.water.target_ml} ml` : ""}
            </Text>
            <View style={{ flexDirection: "row", gap: 10 }}>
              {QUICK_ADD_WATER_ML.map((amount) => (
                <Pressable
                  key={amount}
                  style={screenStyles.secondaryButton}
                  onPress={() => void handleAddWater(amount)}
                >
                  <Text style={screenStyles.secondaryButtonText}>+{amount} ml</Text>
                </Pressable>
              ))}
            </View>
          </View>

          <View style={screenStyles.card}>
            <Text style={screenStyles.cardTitle}>Weight</Text>
            <Text style={screenStyles.body}>
              {dashboard.latest_weight_kg !== null
                ? `${dashboard.latest_weight_kg} kg as of ${dashboard.latest_weight_logged_at}`
                : "No weight logged yet — log one from the Progress tab."}
            </Text>
          </View>
        </>
      ) : null}

      {recommendations.length > 0 ? (
        <View style={screenStyles.card}>
          <Text style={screenStyles.cardTitle}>Insights</Text>
          {recommendations.map((rec, index) => (
            <View
              key={`${rec.category}-${index}`}
              style={{
                borderLeftWidth: 3,
                borderLeftColor: PRIORITY_COLOR[rec.priority],
                paddingLeft: 10,
                gap: 2,
              }}
            >
              <Text style={[screenStyles.body, { fontWeight: "600", color: "#111827" }]}>
                {rec.title}
              </Text>
              <Text style={screenStyles.body}>{rec.detail}</Text>
            </View>
          ))}
        </View>
      ) : null}

      <View style={screenStyles.disclaimerBox}>
        <Text style={screenStyles.disclaimerText}>
          Fitora provides general fitness and nutrition information and estimates. It is not
          medical advice and is not a substitute for a qualified healthcare professional.
        </Text>
      </View>

      <Text style={screenStyles.body}>Signed in as {user?.email}</Text>

      <Pressable
        style={screenStyles.secondaryButton}
        onPress={() => router.push("/settings")}
        accessibilityRole="button"
        accessibilityLabel="Settings and privacy"
      >
        <Text style={screenStyles.secondaryButtonText}>Settings & privacy</Text>
      </Pressable>

      <Pressable
        style={screenStyles.secondaryButton}
        onPress={() => void logout()}
        accessibilityRole="button"
      >
        <Text style={screenStyles.secondaryButtonText}>Log out</Text>
      </Pressable>
    </ScrollView>
  );
}

function MacroRow({
  label,
  value,
  unit,
}: {
  label: string;
  value: { target_g: number | null; consumed_g: number };
  unit: string;
}): React.JSX.Element {
  return (
    <View style={screenStyles.row}>
      <Text style={screenStyles.body}>{label}</Text>
      <Text style={screenStyles.body}>
        {Math.round(value.consumed_g)}
        {unit} / {value.target_g !== null ? `${value.target_g}${unit}` : "—"}
      </Text>
    </View>
  );
}
