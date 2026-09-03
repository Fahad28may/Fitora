import { apiRequest } from "./client";
import type { GoalCreateRequest, GoalOut } from "./types";

export const goalsApi = {
  create: (payload: GoalCreateRequest): Promise<GoalOut> =>
    apiRequest<GoalOut>("/api/v1/goals", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getActive: (): Promise<GoalOut | null> => apiRequest<GoalOut | null>("/api/v1/goals/active"),
};
