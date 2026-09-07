import { apiRequest } from "./client";
import type { FoodDiaryEntryOut, LogUnit, MealCategory } from "./types";

export interface MealItemOut {
  id: string;
  food_id: string;
  food_name: string;
  quantity: number;
  unit: LogUnit;
  calories_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface MealOut {
  id: string;
  name: string;
  created_at: string;
  items: MealItemOut[];
  total_calories_kcal: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
}

export interface MealItemCreateRequest {
  food_id: string;
  quantity: number;
  unit: LogUnit;
}

export const mealsApi = {
  list: (): Promise<MealOut[]> => apiRequest<MealOut[]>("/api/v1/meals"),

  create: (name: string, items: MealItemCreateRequest[]): Promise<MealOut> =>
    apiRequest<MealOut>("/api/v1/meals", {
      method: "POST",
      body: JSON.stringify({ name, items }),
    }),

  /** Expands the meal into one diary entry per item and returns them. */
  log: (
    mealId: string,
    loggedAt: string,
    mealCategory: MealCategory,
  ): Promise<FoodDiaryEntryOut[]> =>
    apiRequest<FoodDiaryEntryOut[]>(`/api/v1/meals/${mealId}/log`, {
      method: "POST",
      body: JSON.stringify({ logged_at: loggedAt, meal_category: mealCategory }),
    }),

  remove: (mealId: string): Promise<void> =>
    apiRequest<void>(`/api/v1/meals/${mealId}`, { method: "DELETE" }),
};
