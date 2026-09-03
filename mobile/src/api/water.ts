import { apiRequest } from "./client";

export interface WaterEntryOut {
  id: string;
  logged_at: string;
  amount_ml: number;
  created_at: string;
}

export const waterApi = {
  create: (loggedAt: string, amountMl: number): Promise<WaterEntryOut> =>
    apiRequest<WaterEntryOut>("/api/v1/water-entries", {
      method: "POST",
      body: JSON.stringify({ logged_at: loggedAt, amount_ml: amountMl }),
    }),

  listForDate: (isoDate: string): Promise<WaterEntryOut[]> =>
    apiRequest<WaterEntryOut[]>(`/api/v1/water-entries?date=${isoDate}`),

  remove: (id: string): Promise<void> =>
    apiRequest<void>(`/api/v1/water-entries/${id}`, { method: "DELETE" }),
};
