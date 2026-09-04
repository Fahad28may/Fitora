import { StyleSheet, Text, View } from "react-native";

export type TrendPoint = {
  /** Short label shown under the first and last bars (e.g. a date). */
  label: string;
  value: number;
};

const CHART_HEIGHT = 120;
// Even the smallest value keeps a visible stub so every point reads as a bar.
const MIN_BAR_FRACTION = 0.08;
const MAX_BARS = 14;

/**
 * Dependency-free trend chart: a row of normalized bars. Intentionally avoids
 * a charting/SVG library so the mobile app keeps its current dependency set.
 * Points are given oldest-to-newest.
 */
export function TrendChart({
  title,
  unit,
  points,
}: {
  title: string;
  unit: string;
  points: TrendPoint[];
}): React.JSX.Element | null {
  // A single point isn't a trend; the caller decides whether to render.
  if (points.length < 2) return null;

  const shown = points.slice(-MAX_BARS);
  const values = shown.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;

  const first = shown[0];
  const last = shown[shown.length - 1];
  const delta = last.value - first.value;
  const deltaLabel = `${delta > 0 ? "+" : ""}${delta.toFixed(1)}${unit}`;

  const fractionFor = (value: number): number => {
    // Flat series (range 0) sits at mid-height rather than dividing by zero.
    const norm = range === 0 ? 0.5 : (value - min) / range;
    return MIN_BAR_FRACTION + norm * (1 - MIN_BAR_FRACTION);
  };

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.delta}>{deltaLabel}</Text>
      </View>

      <View style={styles.plot}>
        <View style={styles.axis}>
          <Text style={styles.axisLabel}>
            {max}
            {unit}
          </Text>
          <Text style={styles.axisLabel}>
            {min}
            {unit}
          </Text>
        </View>
        <View style={styles.bars}>
          {shown.map((point, index) => (
            <View key={index} style={styles.barSlot}>
              <View style={[styles.bar, { height: CHART_HEIGHT * fractionFor(point.value) }]} />
            </View>
          ))}
        </View>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerLabel}>{first.label}</Text>
        <Text style={styles.footerLabel}>
          {last.value}
          {unit}
        </Text>
        <Text style={styles.footerLabel}>{last.label}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    padding: 16,
    gap: 10,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    fontSize: 16,
    fontWeight: "700",
  },
  delta: {
    fontSize: 14,
    fontWeight: "600",
    color: "#6b7280",
  },
  plot: {
    flexDirection: "row",
    height: CHART_HEIGHT,
    gap: 8,
  },
  axis: {
    justifyContent: "space-between",
    paddingVertical: 2,
  },
  axisLabel: {
    fontSize: 11,
    color: "#9ca3af",
  },
  bars: {
    flex: 1,
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 4,
  },
  barSlot: {
    flex: 1,
    height: CHART_HEIGHT,
    justifyContent: "flex-end",
  },
  bar: {
    backgroundColor: "#111827",
    borderRadius: 3,
    minHeight: 4,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  footerLabel: {
    fontSize: 12,
    color: "#6b7280",
  },
});
