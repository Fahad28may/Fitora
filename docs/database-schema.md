# Database Schema

PostgreSQL. All primary keys are UUIDv4 unless noted. All tables have `created_at` / `updated_at` timestamps (UTC). Every user-owned table has a `user_id` foreign key with `ON DELETE CASCADE` (or explicit anonymization — see [`data-flow.md`](data-flow.md)) and an index on `user_id`.

This is the Phase 1–2 schema. Phase 3+ tables (AI conversations) are included since they're architecturally load-bearing, but not built until Phase 3.

## Core identity

### `users`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| email | citext, unique, indexed | |
| password_hash | text | Argon2id, never returned in any response |
| email_verified_at | timestamptz, nullable | |
| status | enum(active, suspended, pending_deletion) | |
| created_at / updated_at | timestamptz | |

### `user_profiles`
| Column | Type | Notes |
|---|---|---|
| user_id | uuid PK/FK → users | 1:1 |
| display_name | text, nullable | |
| date_of_birth | date, nullable | used only for age in BMR calc; age 18+ enforced at signup |
| sex | enum, nullable | used only for BMR formula selection |
| height_cm | numeric, nullable | |
| activity_level | enum(sedentary..very_active), nullable | |
| unit_system | enum(metric, imperial) | display preference |

### `user_sessions`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK | indexed |
| refresh_token_hash | text | never store raw token |
| user_agent | text, nullable | |
| ip_hash | text, nullable | hashed, not raw IP |
| issued_at / expires_at / revoked_at | timestamptz | rotation: issuing a new refresh token revokes the old one |

### `consent_records`
| user_id | consent_type | granted | recorded_at | policy_version |
|---|---|---|---|---|
FK → users. One row per consent decision (health data, AI processing, optional analytics, wearable access). Append-only.

### `audit_events`
| id | user_id (nullable for system events) | event_type | metadata (jsonb, no sensitive payloads) | created_at |
Security-sensitive only: login, password change, account deletion, consent change, security-setting change, suspicious auth activity.

## Goals

### `goals`
| id | user_id FK | goal_type (lose/gain/maintain weight, custom) | target_weight_kg (nullable) | target_calories | target_protein_g | target_carbs_g | target_fat_g | target_water_ml | starts_at | ends_at (nullable) | is_active |
Deterministically computed by the backend calorie-calculation service (see `docs/ai-safety.md` §"No AI for core data"), never by the LLM.

## Nutrition

### `foods`
| id | source (enum: system, user, external_db) | owner_user_id (nullable, set when source=user) | name | brand (nullable) | barcode (nullable, indexed) | serving_description | serving_grams (nullable) |

### `food_nutrition`
| food_id PK/FK → foods | calories_kcal | protein_g | carbs_g | fat_g | fiber_g (nullable) | per_grams (basis, e.g. per 100g or per serving) |

### `meals`
User-created reusable meal templates ("My Breakfast").
| id | user_id FK | name | created_at |

### `meal_items`
| id | meal_id FK (nullable) | food_diary_entry_id FK (nullable) | food_id FK | quantity | unit | grams_equivalent |
Exactly one of `meal_id` / `food_diary_entry_id` is set — a meal item belongs either to a reusable meal template or to a logged diary entry, not both.

### `food_diary_entries`
The actual log of what a user ate on a given day.
| id | user_id FK, indexed with (user_id, logged_at) | logged_at (date) | meal_category (breakfast/lunch/dinner/snack) | source (search/manual/barcode/nl/photo) | created_via_ai (bool) | ai_confidence (nullable) |

### `recipes` / `recipe_ingredients`
| recipes: id, owner_user_id, name, servings |
| recipe_ingredients: id, recipe_id FK, food_id FK, quantity, unit |

### `water_entries`
| id | user_id FK | logged_at | amount_ml |

## Workouts

### `exercises`
| id | name | muscle_groups (text[]) | equipment (nullable) | instructions | difficulty | exercise_type |
System-seeded library; not user-owned.

### `workouts`
| id | user_id FK | name | workout_type (single/routine/program) | created_at |

### `workout_exercises`
| id | workout_id FK | exercise_id FK | order_index | target_sets | target_reps | target_weight_kg (nullable) |

### `workout_sessions`
Actual performed instance of a workout (log, not template).
| id | user_id FK | workout_id FK (nullable, freeform sessions allowed) | started_at | ended_at | notes |

### `workout_sets`
| id | workout_session_id FK | exercise_id FK | set_number | reps | weight_kg (nullable) | duration_seconds (nullable) | distance_m (nullable) | rest_seconds (nullable) | notes |

## Progress

### `weight_entries`
| id | user_id FK, indexed with (user_id, logged_at) | logged_at | weight_kg |

### `body_measurements`
| id | user_id FK | logged_at | waist_cm, chest_cm, arm_cm, leg_cm, hip_cm (all nullable) |

### `progress_photos`
| id | user_id FK | storage_key (private bucket, never a public URL) | taken_at | deleted_at (nullable, soft delete before hard purge) |

### `activity_entries`
| id | user_id FK | source (manual/apple_health/health_connect/wearable) | logged_at | steps (nullable) | active_calories (nullable) | distance_m (nullable) |
Architecture only in Phase 1; populated once health integrations ship (Phase 4).

## AI (Phase 3+)

### `ai_conversations`
| id | user_id FK | started_at | context_type (coach/food_parse/photo_recognition) |

### `ai_messages`
| id | conversation_id FK | role (user/assistant/tool) | content (text, redacted of PII where possible before storage) | created_at |
Retention and deletion covered in `privacy-policy.md`; deleting an account deletes these.

## Conventions

- Money/quantities: `numeric`, never `float`, for anything used in calculation totals.
- Enums implemented as Postgres enums or check-constrained text, not free text, to keep bad data out.
- Every table above gets a foreign-key constraint to `users` (directly or transitively) so cascading delete/anonymization on account deletion is mechanical, not ad hoc — see `data-flow.md` §"Account deletion".
- No table stores plaintext secrets, tokens, or full images — images live in object storage, DB stores only the storage key.
