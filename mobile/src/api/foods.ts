import { apiRequest } from "./client";
import type { FoodCreateRequest, FoodOut } from "./types";

export const foodsApi = {
  search: (query: string): Promise<FoodOut[]> =>
    apiRequest<FoodOut[]>(`/api/v1/foods/search?q=${encodeURIComponent(query)}`),

  /**
   * Resolve a scanned barcode. Throws ApiError with status 503 when the
   * server has no food database configured, 404 when the product is unknown,
   * and 422 when the provider's nutrition data failed validation.
   */
  lookupBarcode: (barcode: string): Promise<FoodOut> =>
    apiRequest<FoodOut>(`/api/v1/foods/barcode/${encodeURIComponent(barcode)}`),

  create: (payload: FoodCreateRequest): Promise<FoodOut> =>
    apiRequest<FoodOut>("/api/v1/foods", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
