import { apiRequest } from "./client";

export interface PersonalRecord {
  exercise_id: string;
  exercise_name: string;
  best_weight_kg: number;
  reps_at_best: number;
  achieved_at: string;
  total_sets: number;
}

export interface WeeklyVolume {
  week_start: string;
  session_count: number;
  set_count: number;
  total_volume_kg: number;
}

export interface WorkoutProgressOut {
  weeks: number;
  since: string;
  total_sessions: number;
  total_volume_kg: number;
  sessions_per_week: number;
  active_weeks: number;
  personal_records: PersonalRecord[];
  /** One entry per week in the window, including untrained weeks. */
  weekly: WeeklyVolume[];
}

export interface ExerciseProgressionPoint {
  week_start: string;
  best_weight_kg: number;
  reps_at_best: number;
}

export interface ExerciseProgressionOut {
  exercise_id: string;
  exercise_name: string;
  weeks: number;
  points: ExerciseProgressionPoint[];
}

export const workoutProgressApi = {
  get: (weeks?: number): Promise<WorkoutProgressOut> =>
    apiRequest<WorkoutProgressOut>(
      `/api/v1/workouts/progress${weeks ? `?weeks=${weeks}` : ""}`,
    ),

  forExercise: (exerciseId: string, weeks?: number): Promise<ExerciseProgressionOut> =>
    apiRequest<ExerciseProgressionOut>(
      `/api/v1/workouts/progress/exercises/${exerciseId}${weeks ? `?weeks=${weeks}` : ""}`,
    ),
};
