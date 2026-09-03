import { apiRequest } from "./client";

export interface WorkoutSetCreateRequest {
  exercise_id: string;
  set_number: number;
  reps?: number | null;
  weight_kg?: number | null;
  duration_seconds?: number | null;
  distance_m?: number | null;
  rest_seconds?: number | null;
  notes?: string | null;
}

export interface WorkoutSessionCreateRequest {
  workout_id?: string | null;
  started_at: string;
  ended_at: string;
  notes?: string | null;
  sets: WorkoutSetCreateRequest[];
}

export interface WorkoutSetOut {
  id: string;
  exercise_id: string;
  exercise_name: string;
  set_number: number;
  reps: number | null;
  weight_kg: number | null;
  duration_seconds: number | null;
  distance_m: number | null;
  rest_seconds: number | null;
  notes: string | null;
}

export interface WorkoutSessionOut {
  id: string;
  workout_id: string | null;
  started_at: string;
  ended_at: string;
  notes: string | null;
  sets: WorkoutSetOut[];
}

export const workoutSessionsApi = {
  log: (payload: WorkoutSessionCreateRequest): Promise<WorkoutSessionOut> =>
    apiRequest<WorkoutSessionOut>("/api/v1/workout-sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  list: (): Promise<WorkoutSessionOut[]> =>
    apiRequest<WorkoutSessionOut[]>("/api/v1/workout-sessions"),

  remove: (id: string): Promise<void> =>
    apiRequest<void>(`/api/v1/workout-sessions/${id}`, { method: "DELETE" }),
};
