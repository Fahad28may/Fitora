import { apiRequest } from "./client";

export interface ExerciseOut {
  id: string;
  name: string;
  muscle_groups: string[];
  equipment: string | null;
  instructions: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  exercise_type: "strength" | "cardio" | "flexibility" | "balance";
}

export const exercisesApi = {
  search: (query: string): Promise<ExerciseOut[]> =>
    apiRequest<ExerciseOut[]>(`/api/v1/exercises?q=${encodeURIComponent(query)}`),
};
