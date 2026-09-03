import { apiRequest } from "./client";

export interface BodyMeasurementCreateRequest {
  logged_at: string;
  waist_cm?: number | null;
  chest_cm?: number | null;
  arm_cm?: number | null;
  leg_cm?: number | null;
  hip_cm?: number | null;
}

export interface BodyMeasurementOut {
  id: string;
  logged_at: string;
  waist_cm: number | null;
  chest_cm: number | null;
  arm_cm: number | null;
  leg_cm: number | null;
  hip_cm: number | null;
  created_at: string;
}

export const measurementsApi = {
  create: (payload: BodyMeasurementCreateRequest): Promise<BodyMeasurementOut> =>
    apiRequest<BodyMeasurementOut>("/api/v1/measurements", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  list: (): Promise<BodyMeasurementOut[]> =>
    apiRequest<BodyMeasurementOut[]>("/api/v1/measurements"),

  remove: (id: string): Promise<void> =>
    apiRequest<void>(`/api/v1/measurements/${id}`, { method: "DELETE" }),
};
