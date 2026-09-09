import { render, waitFor } from "@testing-library/react-native";

import type { AdaptiveTargetsOut, AnalyticsSummaryOut } from "../../src/api/analytics";
import AnalyticsScreen from "../analytics";

const mockAnalyticsApi = {
  summary: jest.fn(),
  adaptiveTargets: jest.fn(),
};

jest.mock("../../src/api/analytics", () => ({
  analyticsApi: {
    summary: (...a: unknown[]) => mockAnalyticsApi.summary(...a),
    adaptiveTargets: (...a: unknown[]) => mockAnalyticsApi.adaptiveTargets(...a),
  },
}));

jest.mock("expo-router", () => ({
  router: { replace: jest.fn(), back: jest.fn(), push: jest.fn() },
}));

function summary(overrides: Partial<AnalyticsSummaryOut> = {}): AnalyticsSummaryOut {
  return {
    generated_for: "2026-09-09",
    since: "2026-08-11",
    window_days: 30,
    weight_trend: {
      available: false,
      unavailable_reason: "Log your weight on at least two days in this window.",
      points: [],
      entry_days: 0,
      span_days: 0,
      weekly_change_kg: null,
      direction: null,
      fit_quality: null,
      confidence: null,
      goal_projection: null,
      projection_unavailable_reason: null,
    },
    adherence: {
      days_in_window: 30,
      days_food_logged: 0,
      current_streak_days: 0,
      longest_streak_days: 0,
      calories: { days_on_target: 0, days_counted: 0 },
      protein: { days_on_target: 0, days_counted: 0 },
      water: { days_on_target: 0, days_counted: 0 },
      has_active_goal: false,
    },
    macro_split: {
      available: false,
      unavailable_reason: "Log food on at least 3 days to see your macro split.",
      days_counted: 0,
      protein_percent: null,
      carbs_percent: null,
      fat_percent: null,
      target_protein_percent: null,
      target_carbs_percent: null,
      target_fat_percent: null,
    },
    weekday_patterns: [
      {
        weekday: 0,
        label: "Monday",
        days_sampled: 0,
        avg_calories_kcal: null,
        avg_activity_minutes: null,
      },
    ],
    energy_balance: {
      available: false,
      unavailable_reason: "Complete your profile to estimate expenditure.",
      days_counted: 0,
      avg_intake_kcal: null,
      estimated_expenditure_kcal: null,
      net_kcal: null,
      reported_activity_burn_kcal: null,
      note: null,
    },
    ...overrides,
  };
}

function adaptive(overrides: Partial<AdaptiveTargetsOut> = {}): AdaptiveTargetsOut {
  return {
    available: false,
    unavailable_reason: "Set a goal first.",
    confidence: null,
    estimated_maintenance_kcal: null,
    predicted_maintenance_kcal: null,
    current_target_calories: null,
    suggested_target_calories: null,
    suggested_protein_g: null,
    suggested_carbs_g: null,
    suggested_fat_g: null,
    delta_kcal: null,
    basis: null,
    caveats: [],
    ...overrides,
  };
}

beforeEach(() => {
  mockAnalyticsApi.summary.mockReset();
  mockAnalyticsApi.adaptiveTargets.mockReset();
  mockAnalyticsApi.summary.mockResolvedValue(summary());
  mockAnalyticsApi.adaptiveTargets.mockResolvedValue(adaptive());
});

describe("Analytics screen", () => {
  it("shows the server's reason rather than a fabricated number", async () => {
    const view = await render(<AnalyticsScreen />);

    await waitFor(() => {
      expect(
        view.getByText("Log your weight on at least two days in this window."),
      ).toBeTruthy();
    });
    expect(
      view.getByText("Log food on at least 3 days to see your macro split."),
    ).toBeTruthy();
    expect(view.getByText("Complete your profile to estimate expenditure.")).toBeTruthy();
  });

  it("states adherence as days-of-days, never as a bare percentage", async () => {
    mockAnalyticsApi.summary.mockResolvedValue(
      summary({
        adherence: {
          days_in_window: 30,
          days_food_logged: 12,
          current_streak_days: 4,
          longest_streak_days: 7,
          calories: { days_on_target: 8, days_counted: 12 },
          protein: { days_on_target: 5, days_counted: 12 },
          water: { days_on_target: 2, days_counted: 3 },
          has_active_goal: true,
        },
      }),
    );

    const view = await render(<AnalyticsScreen />);

    // "8 of 12" and "2 of 3" are different claims from a shared "67%".
    await waitFor(() => expect(view.getByText("8 of 12 days")).toBeTruthy());
    expect(view.getByText("2 of 3 days")).toBeTruthy();
  });

  it("shows a weight rate with its confidence attached", async () => {
    mockAnalyticsApi.summary.mockResolvedValue(
      summary({
        weight_trend: {
          available: true,
          unavailable_reason: null,
          points: [
            { date: "2026-08-12", weight_kg: 80.0, trend_kg: 80.0 },
            { date: "2026-08-26", weight_kg: 79.5, trend_kg: 79.8 },
            { date: "2026-09-09", weight_kg: 79.0, trend_kg: 79.4 },
          ],
          entry_days: 3,
          span_days: 28,
          weekly_change_kg: -0.25,
          direction: "falling",
          fit_quality: 0.94,
          confidence: "moderate",
          goal_projection: null,
          projection_unavailable_reason: "Set a goal weight to see a projection.",
        },
      }),
    );

    const view = await render(<AnalyticsScreen />);

    await waitFor(() => expect(view.getByText(/0\.25 kg a week/)).toBeTruthy());
    expect(view.getByText("moderate confidence in this estimate")).toBeTruthy();
    expect(view.getByText("Set a goal weight to see a projection.")).toBeTruthy();
  });

  it("presents an adaptive target as a suggestion that has not been applied", async () => {
    mockAnalyticsApi.adaptiveTargets.mockResolvedValue(
      adaptive({
        available: true,
        unavailable_reason: null,
        confidence: "high",
        estimated_maintenance_kcal: 2775,
        predicted_maintenance_kcal: 2750,
        current_target_calories: 2400,
        suggested_target_calories: 2775,
        delta_kcal: 375,
        caveats: ["Nothing changes until you set a new goal yourself."],
      }),
    );

    const view = await render(<AnalyticsScreen />);

    await waitFor(() => expect(view.getByText(/2775 kcal \(\+375\)/)).toBeTruthy());
    expect(
      view.getByText("Nothing changes until you set a new goal yourself."),
    ).toBeTruthy();
    expect(view.getByText(/will not change your target for you/)).toBeTruthy();
  });

  it("still renders the summary when the adaptive estimate fails", async () => {
    mockAnalyticsApi.adaptiveTargets.mockRejectedValue(new Error("boom"));

    const view = await render(<AnalyticsScreen />);

    await waitFor(() =>
      expect(
        view.getByText("Log food on at least 3 days to see your macro split."),
      ).toBeTruthy(),
    );
  });

  it("reports a failure instead of rendering an empty screen", async () => {
    mockAnalyticsApi.summary.mockRejectedValue(new Error("boom"));

    const view = await render(<AnalyticsScreen />);

    await waitFor(() => expect(view.getByText("Could not load your analytics.")).toBeTruthy());
  });
});
