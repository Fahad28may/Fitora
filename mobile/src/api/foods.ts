import { apiRequest } from "./client";
import type { FoodCreateRequest, FoodOut } from "./types";

export const foodsApi = {
  /**
   * `includeExternal` sends the search term to the server's configured food
   * database (a third party). It defaults to false and the UI asks for it
   * explicitly — unlike a barcode, the term is free text the user typed.
   * Throws ApiError with status 503 when asked for and no provider is
   * configured.
   */
  search: (query: string, options?: { includeExternal?: boolean }): Promise<FoodOut[]> =>
    apiRequest<FoodOut[]>(
      `/api/v1/foods/search?q=${encodeURIComponent(query)}` +
        (options?.includeExternal ? "&include_external=true" : ""),
    ),

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
