import { apiRequest } from "./client";

export type Confidence = "low" | "moderate" | "high";
export type TrendDirection = "falling" | "steady" | "rising";

export interface WeightTrendPoint {
  date: string;
  /** The day's logged weight. Never interpolated — days without a weigh-in produce no point. */
  weight_kg: number;
  trend_kg: number;
}

export interface GoalProjection {
  target_weight_kg: number;
  estimated_weeks: number;
  estimated_date: string;
  caveat: string;
}

export interface WeightTrendOut {
  available: boolean;
  unavailable_reason: string | null;
  points: WeightTrendPoint[];
  entry_days: number;
  span_days: number;
  /** null when there aren't enough weigh-ins, over enough time, to fit a rate. */
  weekly_change_kg: number | null;
  direction: TrendDirection | null;
  fit_quality: number | null;
  confidence: Confidence | null;
  goal_projection: GoalProjection | null;
  projection_unavailable_reason: string | null;
}

/** Days on target out of days that could be judged — both numbers, never a bare percentage. */
export interface TargetAdherence {
  days_on_target: number;
  days_counted: number;
}

export interface AdherenceOut {
  days_in_window: number;
  days_food_logged: number;
  current_streak_days: number;
  longest_streak_days: number;
  calories: TargetAdherence;
  protein: TargetAdherence;
  water: TargetAdherence;
  has_active_goal: boolean;
}

export interface MacroSplitOut {
  available: boolean;
  unavailable_reason: string | null;
  days_counted: number;
  protein_percent: number | null;
  carbs_percent: number | null;
  fat_percent: number | null;
  target_protein_percent: number | null;
  target_carbs_percent: number | null;
  target_fat_percent: number | null;
}

export interface WeekdayPattern {
  /** 0 = Monday. */
  weekday: number;
  label: string;
  days_sampled: number;
  /** null when nothing was logged on that weekday — not 0, which would claim the user ate nothing. */
  avg_calories_kcal: number | null;
  avg_activity_minutes: number | null;
}

export interface EnergyBalanceOut {
  available: boolean;
  unavailable_reason: string | null;
  days_counted: number;
  avg_intake_kcal: number | null;
  estimated_expenditure_kcal: number | null;
  net_kcal: number | null;
  /** Shown for context and deliberately not added to expenditure — see `note`. */
  reported_activity_burn_kcal: number | null;
  note: string | null;
}

export interface AnalyticsSummaryOut {
  generated_for: string;
  since: string;
  window_days: number;
  weight_trend: WeightTrendOut;
  adherence: AdherenceOut;
  macro_split: MacroSplitOut;
  weekday_patterns: WeekdayPattern[];
  energy_balance: EnergyBalanceOut;
}

export interface AdaptiveTargetBasis {
  window_days: number;
  span_days: number;
  days_with_food_logged: number;
  weigh_in_days: number;
  avg_intake_kcal: number;
  weight_change_kg: number;
}

export interface AdaptiveTargetsOut {
  available: boolean;
  unavailable_reason: string | null;
  confidence: Confidence | null;
  estimated_maintenance_kcal: number | null;
  predicted_maintenance_kcal: number | null;
  current_target_calories: number | null;
  suggested_target_calories: number | null;
  suggested_protein_g: number | null;
  suggested_carbs_g: number | null;
  suggested_fat_g: number | null;
  delta_kcal: number | null;
  basis: AdaptiveTargetBasis | null;
  caveats: string[];
}

export const analyticsApi = {
  summary: (days?: number): Promise<AnalyticsSummaryOut> =>
    apiRequest<AnalyticsSummaryOut>(
      `/api/v1/analytics/summary${days ? `?days=${days}` : ""}`,
    ),

  /**
   * A calorie target proposed from the user's own intake and weight history.
   * Advisory only — the server never applies it, and neither does this client.
   */
  adaptiveTargets: (): Promise<AdaptiveTargetsOut> =>
    apiRequest<AdaptiveTargetsOut>("/api/v1/analytics/adaptive-targets"),
};
