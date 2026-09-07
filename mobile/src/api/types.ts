export interface UserOut {
  id: string;
  email: string;
  email_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: UserOut;
  tokens: TokenResponse;
}

export type Sex = "male" | "female";
export type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type UnitSystem = "metric" | "imperial";

export interface ProfileOut {
  display_name: string | null;
  date_of_birth: string | null;
  sex: Sex | null;
  height_cm: number | null;
  activity_level: ActivityLevel | null;
  unit_system: UnitSystem;
}

export interface ProfileUpdateRequest {
  display_name?: string | null;
  date_of_birth: string;
  sex: Sex;
  height_cm: number;
  activity_level: ActivityLevel;
  unit_system: UnitSystem;
}

export type GoalType = "lose_weight" | "maintain_weight" | "gain_weight";
export type GoalIntensity = "light" | "standard" | "aggressive";

export interface GoalCreateRequest {
  goal_type: GoalType;
  intensity: GoalIntensity;
  current_weight_kg: number;
  target_weight_kg?: number | null;
  acknowledge_risk?: boolean;
}

export interface GoalOut {
  id: string;
  goal_type: GoalType;
  intensity: GoalIntensity;
  target_weight_kg: number | null;
  target_calories: number;
  target_protein_g: number;
  target_carbs_g: number;
  target_fat_g: number;
  target_water_ml: number;
  is_active: boolean;
  created_at: string;
}

export interface UnsafeGoalDetail {
  is_safe: boolean;
  warnings: string[];
  safer_alternative_calories: number | null;
}

export interface WeightEntryCreateRequest {
  logged_at: string;
  weight_kg: number;
}

export interface WeightEntryOut {
  id: string;
  logged_at: string;
  weight_kg: number;
  created_at: string;
}

export interface FoodCreateRequest {
  name: string;
  brand?: string | null;
  serving_description: string;
  serving_grams: number;
  calories_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g?: number | null;
}

export interface FoodOut {
  id: string;
  source: "system" | "user" | "external_db";
  name: string;
  brand: string | null;
  serving_description: string;
  serving_grams: number | null;
  calories_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number | null;
}

export type MealCategory = "breakfast" | "lunch" | "dinner" | "snack";
export type LogUnit = "serving" | "gram";
export type LogSource = "search" | "manual" | "barcode" | "natural_language" | "photo";

export interface FoodDiaryEntryCreateRequest {
  food_id: string;
  logged_at: string;
  meal_category: MealCategory;
  quantity: number;
  unit: LogUnit;
  /** How the food was picked. Defaults to "manual" server-side. */
  source?: LogSource;
}

export interface FoodDiaryEntryOut {
  id: string;
  food_id: string;
  food_name: string;
  logged_at: string;
  meal_category: MealCategory;
  quantity: number;
  unit: LogUnit;
  source: string;
  calories_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number | null;
  created_at: string;
}

export interface MacroProgress {
  target_g: number | null;
  consumed_g: number;
}

export interface CalorieProgress {
  target: number | null;
  consumed: number;
  remaining: number | null;
}

export interface WaterProgress {
  target_ml: number | null;
  consumed_ml: number;
}

export interface DashboardOut {
  date: string;
  has_profile: boolean;
  has_active_goal: boolean;
  calories: CalorieProgress;
  protein: MacroProgress;
  carbs: MacroProgress;
  fat: MacroProgress;
  water: WaterProgress;
  latest_weight_kg: number | null;
  latest_weight_logged_at: string | null;
}
