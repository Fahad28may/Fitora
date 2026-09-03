import { apiRequest } from "./client";
import type { DashboardOut } from "./types";

export const dashboardApi = {
  get: (isoDate?: string): Promise<DashboardOut> =>
    apiRequest<DashboardOut>(isoDate ? `/api/v1/dashboard?date=${isoDate}` : "/api/v1/dashboard"),
};
