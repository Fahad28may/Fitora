import { apiRequest } from "./client";

export type RecommendationCategory =
  | "nutrition"
  | "hydration"
  | "activity"
  | "weight"
  | "consistency";

export type RecommendationPriority = "info" | "suggestion" | "warning";

export type Recommendation = {
  category: RecommendationCategory;
  priority: RecommendationPriority;
  title: string;
  detail: string;
};

export type RecommendationsOut = {
  generated_for: string;
  window_days: number;
  days_with_food_logged: number;
  has_active_goal: boolean;
  recommendations: Recommendation[];
};

export const recommendationsApi = {
  get: (isoDate?: string): Promise<RecommendationsOut> =>
    apiRequest<RecommendationsOut>(
      isoDate ? `/api/v1/recommendations?date=${isoDate}` : "/api/v1/recommendations",
    ),
};
