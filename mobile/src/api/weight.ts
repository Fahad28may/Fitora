import { apiRequest } from "./client";
import type { WeightEntryCreateRequest, WeightEntryOut } from "./types";

export const weightApi = {
  create: (payload: WeightEntryCreateRequest): Promise<WeightEntryOut> =>
    apiRequest<WeightEntryOut>("/api/v1/weight-entries", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  list: (): Promise<WeightEntryOut[]> => apiRequest<WeightEntryOut[]>("/api/v1/weight-entries"),

  remove: (id: string): Promise<void> =>
    apiRequest<void>(`/api/v1/weight-entries/${id}`, { method: "DELETE" }),
};
