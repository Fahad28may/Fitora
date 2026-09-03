import { apiRequest } from "./client";
import type { FoodCreateRequest, FoodOut } from "./types";

export const foodsApi = {
  search: (query: string): Promise<FoodOut[]> =>
    apiRequest<FoodOut[]>(`/api/v1/foods/search?q=${encodeURIComponent(query)}`),

  create: (payload: FoodCreateRequest): Promise<FoodOut> =>
    apiRequest<FoodOut>("/api/v1/foods", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
