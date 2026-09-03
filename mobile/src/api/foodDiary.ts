import { apiRequest } from "./client";
import type { FoodDiaryEntryCreateRequest, FoodDiaryEntryOut } from "./types";

export const foodDiaryApi = {
  create: (payload: FoodDiaryEntryCreateRequest): Promise<FoodDiaryEntryOut> =>
    apiRequest<FoodDiaryEntryOut>("/api/v1/food-diary", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listForDate: (isoDate: string): Promise<FoodDiaryEntryOut[]> =>
    apiRequest<FoodDiaryEntryOut[]>(`/api/v1/food-diary?date=${isoDate}`),

  remove: (id: string): Promise<void> =>
    apiRequest<void>(`/api/v1/food-diary/${id}`, { method: "DELETE" }),
};
