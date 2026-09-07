import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import { dashboardApi } from "../../src/api/dashboard";
import { outbox } from "../../src/api/outbox";
import type { Recommendation, RecommendationPriority } from "../../src/api/recommendations";
import { recommendationsApi } from "../../src/api/recommendations";
import type { DashboardOut } from "../../src/api/types";
import { useAuth } from "../../src/auth/AuthContext";
import { todayIso } from "../../src/utils/date";
import { screenStyles } from "./styles";

const QUICK_ADD_WATER_ML = [250, 500];

const PRIORITY_COLOR: Record<RecommendationPriority, string> = {
  warning: "#dc2626",
  suggestion: "#2563eb",
  info: "#059669",
};

// §44: never communicate important information through colour alone. The
// coloured rule is decoration; this word is what actually carries the
// priority, for anyone who can't distinguish the colours or is using a
// screen reader.
const PRIORITY_LABEL: Record<RecommendationPriority, string> = {
  warning: "Worth attention",
  suggestion: "Suggestion",
  info: "Note",
};

export default function HomeScreen(): React.JSX.Element {
  const { user, logout } = useAuth();
  const [dashboard, setDashboard] = useState<DashboardOut | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const load = useCallback(async () => {
    try {
      // Anything queued while offline goes out before the dashboard is read,
      // so the numbers below already include it rather than appearing to
      // have lost the user's logs.
      await outbox.flush();
      setPendingCount(await outbox.count());
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
    // Goes through the outbox: if the network is down the write is queued
    // with a stable idempotency key and replayed later, so a flaky
    // connection can't turn one tap into two logged drinks.
    await outbox.send(
      "/api/v1/water-entries",
      { logged_at: todayIso(), amount_ml: amountMl },
      `${amountMl} ml of water`,
    );
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

      {pendingCount > 0 ? (
        <View style={screenStyles.card} accessible accessibilityRole="alert">
          <Text style={screenStyles.cardTitle}>
            {pendingCount} {pendingCount === 1 ? "entry" : "entries"} waiting to sync
          </Text>
          <Text style={screenStyles.body}>
            Saved on this device. They&apos;ll be sent automatically next time you have a
            connection — pull down to try now.
          </Text>
        </View>
      ) : null}

      {needsSetup ? (
        <Pressable
          style={screenStyles.setupCard}
          accessibilityRole="button"
          accessibilityLabel="Finish setting up your profile and goal"
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
                  accessibilityRole="button"
                  accessibilityLabel={`Add ${amount} millilitres of water`}
                >
                  <Text style={screenStyles.secondaryButtonText}>+{amount} ml</Text>
                </Pressable>
              ))}
            </View>
          </View>

          <View style={screenStyles.card}>
            <Text style={screenStyles.cardTitle}>Activity</Text>
            {dashboard.activity.entry_count === 0 ? (
              <Text style={screenStyles.body}>Nothing logged today.</Text>
            ) : (
              <>
                <Text style={screenStyles.body}>
                  {dashboard.activity.entry_count}{" "}
                  {dashboard.activity.entry_count === 1 ? "activity" : "activities"} ·{" "}
                  {dashboard.activity.duration_min} min
                </Text>
                {/* Steps are shown only when something reported them. A "0
                    steps" line would assert the user didn't move, which isn't
                    a claim the app can make without a device integration. */}
                {dashboard.activity.steps !== null ? (
                  <Text style={screenStyles.body}>
                    {dashboard.activity.steps.toLocaleString()} steps
                  </Text>
                ) : null}
                {dashboard.activity.calories_burned !== null ? (
                  <Text style={screenStyles.body}>
                    ~{dashboard.activity.calories_burned} kcal burned (your estimate)
                  </Text>
                ) : null}
              </>
            )}
          </View>

          <View style={screenStyles.card}>
            <Text style={screenStyles.cardTitle}>Today&apos;s workout</Text>
            {dashboard.todays_workouts.length === 0 ? (
              <Text style={screenStyles.body}>
                No session logged today — start one from the Workout tab.
              </Text>
            ) : (
              dashboard.todays_workouts.map((session) => (
                <Text key={session.session_id} style={screenStyles.body}>
                  {session.workout_name ?? "Freeform session"} · {session.set_count} sets
                  {session.total_volume_kg > 0
                    ? ` · ${session.total_volume_kg.toLocaleString()} kg lifted`
                    : ""}
                </Text>
              ))
            )}
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
              accessible
              accessibilityLabel={`${PRIORITY_LABEL[rec.priority]}: ${rec.title}. ${rec.detail}`}
              style={{
                borderLeftWidth: 3,
                borderLeftColor: PRIORITY_COLOR[rec.priority],
                paddingLeft: 10,
                gap: 2,
              }}
            >
              <Text
                style={[
                  screenStyles.body,
                  { fontWeight: "600", color: PRIORITY_COLOR[rec.priority], fontSize: 12 },
                ]}
              >
                {PRIORITY_LABEL[rec.priority].toUpperCase()}
              </Text>
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
