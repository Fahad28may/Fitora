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

export type RecognitionConfidence = "high" | "medium" | "low";

export interface RecognizedFoodItemOut {
  name: string;
  estimated_quantity: number;
  unit: string;
  portion_note: string;
  /** Always a range — the API has no single exact-calorie field by design. */
  calories_min: number;
  calories_max: number;
  confidence: RecognitionConfidence;
  ingredients: string[];
  matches: FoodOut[];
}

export interface PhotoRecognitionOut {
  items: RecognizedFoodItemOut[];
  overall_note: string;
  is_estimate: boolean;
  image_retained: boolean;
}

/**
 * Send a photo for food recognition. The image is uploaded, processed, and
 * dropped server-side — it is never stored, and nothing is logged until the
 * user confirms a match.
 */
export async function recognizeFoodPhoto(
  uri: string,
  mimeType: string,
): Promise<PhotoRecognitionOut> {
  const form = new FormData();
  form.append("file", {
    uri,
    name: mimeType === "image/png" ? "meal.png" : "meal.jpg",
    type: mimeType,
  } as unknown as Blob);
  return apiRequest<PhotoRecognitionOut>("/api/v1/ai/recognize-food", {
    method: "POST",
    body: form,
  });
}
