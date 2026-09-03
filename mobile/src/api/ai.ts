import { apiRequest } from "./client";
import type { FoodOut } from "./types";

export interface ParsedFoodItemOut {
  name: string;
  quantity: number;
  unit: string;
  matches: FoodOut[];
}

export interface FoodParseResponse {
  items: ParsedFoodItemOut[];
}

export interface CoachMessageOut {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export const aiApi = {
  parseFood: (text: string): Promise<FoodParseResponse> =>
    apiRequest<FoodParseResponse>("/api/v1/ai/parse-food", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  sendCoachMessage: (message: string): Promise<CoachMessageOut> =>
    apiRequest<CoachMessageOut>("/api/v1/ai/coach/messages", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  listCoachMessages: (): Promise<CoachMessageOut[]> =>
    apiRequest<CoachMessageOut[]>("/api/v1/ai/coach/messages"),

  clearCoachMessages: (): Promise<void> =>
    apiRequest<void>("/api/v1/ai/coach/messages", { method: "DELETE" }),
};
