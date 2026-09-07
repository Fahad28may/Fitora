import { apiRequest } from "./client";

export interface DailyHistoryPoint {
  date: string;
  calories_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  water_ml: number;
  activity_minutes: number;
  /** null (not 0) when nothing reported steps that day. */
  steps: number | null;
}

export interface HistoryOut {
  days: number;
  since: string;
  /** One point per day in the window, including days with nothing logged. */
  points: DailyHistoryPoint[];
}

export const historyApi = {
  get: (days?: number): Promise<HistoryOut> =>
    apiRequest<HistoryOut>(`/api/v1/dashboard/history${days ? `?days=${days}` : ""}`),
};
