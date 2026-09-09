import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import type {
  AdaptiveTargetsOut,
  AdherenceOut,
  AnalyticsSummaryOut,
  EnergyBalanceOut,
  MacroSplitOut,
  TargetAdherence,
  WeekdayPattern,
  WeightTrendOut,
} from "../src/api/analytics";
import { analyticsApi } from "../src/api/analytics";
import { formStyles as s } from "../src/ui/formStyles";
import { TrendChart } from "../src/ui/TrendChart";
import { screenStyles } from "./(tabs)/styles";

const DIRECTION_LABEL: Record<string, string> = {
  falling: "trending down",
  steady: "holding steady",
  rising: "trending up",
};

/**
 * Every block here mirrors the server's own honesty rules: when a section is
 * unavailable it says why in the server's words rather than rendering an empty
 * chart or a zero. Confidence is always shown next to a derived number.
 */
export default function AnalyticsScreen(): React.JSX.Element {
  const [summary, setSummary] = useState<AnalyticsSummaryOut | null>(null);
  const [adaptive, setAdaptive] = useState<AdaptiveTargetsOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [summaryData, adaptiveData] = await Promise.all([
        analyticsApi.summary(),
        // The adaptive suggestion is an extra; losing it must not blank the
        // rest of the screen.
        analyticsApi.adaptiveTargets().catch(() => null),
      ]);
      setSummary(summaryData);
      setAdaptive(adaptiveData);
    } catch {
      setError("Could not load your analytics.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount: setState happens after the awaited API call resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return (
    <ScrollView contentContainerStyle={screenStyles.container}>
      <Text style={screenStyles.title}>Analytics</Text>

      {isLoading ? <ActivityIndicator /> : null}
      {error ? <Text style={s.error}>{error}</Text> : null}

      {summary ? (
        <>
          <Text style={screenStyles.body}>
            Last {summary.window_days} days, from {summary.since}.
          </Text>
          <WeightTrendSection trend={summary.weight_trend} />
          <AdherenceSection adherence={summary.adherence} />
          <MacroSplitSection split={summary.macro_split} />
          <EnergyBalanceSection balance={summary.energy_balance} />
          <WeekdaySection patterns={summary.weekday_patterns} />
        </>
      ) : null}

      {adaptive ? <AdaptiveTargetSection adaptive={adaptive} /> : null}

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

function Unavailable({ reason }: { reason: string | null }): React.JSX.Element {
  return <Text style={screenStyles.body}>{reason ?? "Not enough data yet."}</Text>;
}

function ConfidenceNote({ confidence }: { confidence: string | null }): React.JSX.Element | null {
  if (confidence === null) return null;
  return (
    <Text style={screenStyles.statLabel}>{confidence} confidence in this estimate</Text>
  );
}

function WeightTrendSection({ trend }: { trend: WeightTrendOut }): React.JSX.Element {
  return (
    <View style={screenStyles.card}>
      <Text style={screenStyles.cardTitle}>Weight trend</Text>

      {!trend.available ? (
        <Unavailable reason={trend.unavailable_reason} />
      ) : (
        <>
          {trend.weekly_change_kg === null ? (
            // The points are real; the rate is what the data can't support.
            <Unavailable reason={trend.projection_unavailable_reason} />
          ) : (
            <>
              <Text style={screenStyles.body}>
                About {Math.abs(trend.weekly_change_kg).toFixed(2)} kg a week,{" "}
                {DIRECTION_LABEL[trend.direction ?? "steady"]}, over{" "}
                {trend.entry_days} weigh-ins across {trend.span_days} days.
              </Text>
              <ConfidenceNote confidence={trend.confidence} />
            </>
          )}

          <TrendChart
            title="Smoothed"
            unit="kg"
            points={trend.points.map((p) => ({
              label: p.date.slice(5),
              value: p.trend_kg,
            }))}
          />

          {trend.goal_projection ? (
            <View style={screenStyles.disclaimerBox}>
              <Text style={screenStyles.body}>
                At this rate you&apos;d reach {trend.goal_projection.target_weight_kg} kg around{" "}
                {trend.goal_projection.estimated_date} — about{" "}
                {trend.goal_projection.estimated_weeks} weeks.
              </Text>
              <Text style={screenStyles.disclaimerText}>{trend.goal_projection.caveat}</Text>
            </View>
          ) : trend.projection_unavailable_reason && trend.weekly_change_kg !== null ? (
            <Text style={screenStyles.statLabel}>{trend.projection_unavailable_reason}</Text>
          ) : null}
        </>
      )}
    </View>
  );
}

function AdherenceRow({
  label,
  value,
}: {
  label: string;
  value: TargetAdherence;
}): React.JSX.Element {
  return (
    <View style={screenStyles.row}>
      <Text style={screenStyles.body}>{label}</Text>
      {/* "n of m", never a bare percentage: 4 of 5 logged days and 4 of 30
          days are different claims and a percentage hides which one it is. */}
      <Text style={screenStyles.body}>
        {value.days_counted === 0
          ? "no days to judge"
          : `${value.days_on_target} of ${value.days_counted} days`}
      </Text>
    </View>
  );
}

function AdherenceSection({ adherence }: { adherence: AdherenceOut }): React.JSX.Element {
  return (
    <View style={screenStyles.card}>
      <Text style={screenStyles.cardTitle}>Consistency</Text>
      <View style={screenStyles.statRow}>
        <View style={screenStyles.statBox}>
          <Text style={screenStyles.statValue}>{adherence.current_streak_days}</Text>
          <Text style={screenStyles.statLabel}>day streak</Text>
        </View>
        <View style={screenStyles.statBox}>
          <Text style={screenStyles.statValue}>{adherence.longest_streak_days}</Text>
          <Text style={screenStyles.statLabel}>best streak</Text>
        </View>
        <View style={screenStyles.statBox}>
          <Text style={screenStyles.statValue}>{adherence.days_food_logged}</Text>
          <Text style={screenStyles.statLabel}>days logged</Text>
        </View>
      </View>

      {adherence.has_active_goal ? (
        <>
          <AdherenceRow label="Calories on target" value={adherence.calories} />
          <AdherenceRow label="Protein on target" value={adherence.protein} />
          <AdherenceRow label="Water on target" value={adherence.water} />
        </>
      ) : (
        <Text style={screenStyles.body}>
          Set a goal to see how often you&apos;re hitting your targets.
        </Text>
      )}
    </View>
  );
}

function MacroSplitSection({ split }: { split: MacroSplitOut }): React.JSX.Element {
  return (
    <View style={screenStyles.card}>
      <Text style={screenStyles.cardTitle}>Macro split</Text>
      {!split.available ? (
        <Unavailable reason={split.unavailable_reason} />
      ) : (
        <>
          <Text style={screenStyles.body}>
            Protein {split.protein_percent}% · Carbs {split.carbs_percent}% · Fat{" "}
            {split.fat_percent}%
          </Text>
          {split.target_protein_percent !== null ? (
            <Text style={screenStyles.statLabel}>
              Your targets: protein {split.target_protein_percent}% · carbs{" "}
              {split.target_carbs_percent}% · fat {split.target_fat_percent}%
            </Text>
          ) : null}
          <Text style={screenStyles.statLabel}>From {split.days_counted} logged days</Text>
        </>
      )}
    </View>
  );
}

function EnergyBalanceSection({ balance }: { balance: EnergyBalanceOut }): React.JSX.Element {
  return (
    <View style={screenStyles.card}>
      <Text style={screenStyles.cardTitle}>Energy balance</Text>
      {!balance.available ? (
        <>
          <Unavailable reason={balance.unavailable_reason} />
          {balance.avg_intake_kcal !== null ? (
            <Text style={screenStyles.statLabel}>
              Average intake {Math.round(balance.avg_intake_kcal)} kcal/day
            </Text>
          ) : null}
        </>
      ) : (
        <>
          <Text style={screenStyles.body}>
            You average {Math.round(balance.avg_intake_kcal ?? 0)} kcal a day against an
            estimated {balance.estimated_expenditure_kcal} kcal burned — a net of{" "}
            {(balance.net_kcal ?? 0) > 0 ? "+" : ""}
            {Math.round(balance.net_kcal ?? 0)} kcal.
          </Text>
          {balance.reported_activity_burn_kcal !== null ? (
            <Text style={screenStyles.statLabel}>
              You or your device also reported {balance.reported_activity_burn_kcal} kcal
              burned in activity over this window.
            </Text>
          ) : null}
          {balance.note ? (
            <View style={screenStyles.disclaimerBox}>
              <Text style={screenStyles.disclaimerText}>{balance.note}</Text>
            </View>
          ) : null}
        </>
      )}
    </View>
  );
}

function WeekdaySection({ patterns }: { patterns: WeekdayPattern[] }): React.JSX.Element {
  const sampled = patterns.filter((p) => p.days_sampled > 0);
  return (
    <View style={screenStyles.card}>
      <Text style={screenStyles.cardTitle}>By day of the week</Text>
      {sampled.length === 0 ? (
        <Text style={screenStyles.body}>Nothing logged yet in this window.</Text>
      ) : (
        sampled.map((pattern) => (
          <View key={pattern.weekday} style={screenStyles.row}>
            <Text style={screenStyles.body}>{pattern.label}</Text>
            {/* The sample count travels with the average so a single Saturday
                is not read as a habit. */}
            <Text style={screenStyles.body}>
              {Math.round(pattern.avg_calories_kcal ?? 0)} kcal ({pattern.days_sampled}{" "}
              {pattern.days_sampled === 1 ? "day" : "days"})
            </Text>
          </View>
        ))
      )}
    </View>
  );
}

function AdaptiveTargetSection({
  adaptive,
}: {
  adaptive: AdaptiveTargetsOut;
}): React.JSX.Element {
  return (
    <View style={screenStyles.card}>
      <Text style={screenStyles.cardTitle}>Your own maintenance estimate</Text>
      {!adaptive.available ? (
        <Unavailable reason={adaptive.unavailable_reason} />
      ) : (
        <>
          <Text style={screenStyles.body}>
            Your logging suggests you maintain around {adaptive.estimated_maintenance_kcal}{" "}
            kcal a day
            {adaptive.predicted_maintenance_kcal !== null
              ? `, against ${adaptive.predicted_maintenance_kcal} kcal predicted from your profile`
              : ""}
            .
          </Text>
          <ConfidenceNote confidence={adaptive.confidence} />
          <View style={screenStyles.row}>
            <Text style={screenStyles.body}>Current target</Text>
            <Text style={screenStyles.body}>{adaptive.current_target_calories} kcal</Text>
          </View>
          <View style={screenStyles.row}>
            <Text style={screenStyles.body}>Suggested</Text>
            <Text style={screenStyles.cardTitle}>
              {adaptive.suggested_target_calories} kcal
              {adaptive.delta_kcal !== null && adaptive.delta_kcal !== 0
                ? ` (${adaptive.delta_kcal > 0 ? "+" : ""}${adaptive.delta_kcal})`
                : ""}
            </Text>
          </View>
          <Text style={screenStyles.statLabel}>
            To use this, set a new goal from Settings — Fitora will not change your target
            for you.
          </Text>
        </>
      )}

      {adaptive.caveats.length > 0 ? (
        <View style={screenStyles.disclaimerBox}>
          {adaptive.caveats.map((caveat) => (
            <Text key={caveat} style={screenStyles.disclaimerText}>
              {caveat}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}
