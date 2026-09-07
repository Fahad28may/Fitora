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

**Implemented (Phase 1):** `foods`, `food_nutrition`, `food_diary_entries` below, as built. `meals`/`meal_items` (reusable meal templates) and `recipes`/`recipe_ingredients` are deferred — Phase 1 scope is search/manual food logging, not reusable templates — so `food_diary_entries` references `food_id` directly rather than through a `meal_items` indirection. Revisit this table once meal templates are built, since at that point a shared line-item table (as originally sketched) may be worth the complexity.

### `foods`
| id | source (enum: system, user, external_db) | owner_user_id (nullable, set when source=user) | name (indexed) | brand (nullable) | barcode (nullable, indexed; set on `external_db` rows imported by barcode lookup) | serving_description | serving_grams (nullable for system foods; required when a user creates a custom food, so grams-based scaling is always well-defined) |

`external_db` rows are products imported from Open Food Facts by a barcode scan. They are shared reference data, not user data: `owner_user_id` is null, so they survive an account deletion, and any authenticated user can read one **by id or by barcode** — a repeat scan of the same product is served from this table with no outbound request. They are deliberately excluded from `/foods/search`, so one user cannot discover what another has scanned by typing a product name. No uniqueness constraint on `barcode`: two simultaneous scans of an uncached barcode can each insert a row, which is harmless because lookup orders by `created_at` and so resolves consistently.

### `food_nutrition`
| food_id PK/FK → foods | calories_kcal | protein_g | carbs_g | fat_g | fiber_g (nullable) | per_grams (basis — for user-created foods, equal to serving_grams) |
Nutrition for a logged entry is computed on read (grams logged ÷ per_grams × values), not snapshotted at log time — there's no food-editing endpoint yet, so this doesn't yet risk retroactively changing historical entries in practice, but revisit if/when custom foods become editable.

### `food_diary_entries`
The actual log of what a user ate on a given day. One food per row; logging "breakfast: eggs, toast, coffee" is three rows sharing `logged_at`/`meal_category`.
| id | user_id FK, indexed with (user_id, logged_at) | food_id FK | logged_at (date) | meal_category (breakfast/lunch/dinner/snack) | quantity | unit (serving/gram) | source (search/manual/barcode/nl/photo — only search/manual wired up so far) | created_via_ai (bool) | ai_confidence (nullable) |

### `meals` / `meal_items` — deferred
### `recipes` / `recipe_ingredients` — deferred

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
| id | user_id FK, indexed with (user_id, taken_at) | taken_at | storage_key (unique; opaque key in a private bucket, never a public URL) | content_type | size_bytes |
Delete is immediate and hard — it removes the object from storage and the row (no `deleted_at` soft-delete column). Reads are served only via short-lived presigned URLs generated per request. Access is authorized by row ownership, not key secrecy.

### `activity_entries`
| id | user_id FK, indexed with (user_id, logged_at) | logged_at | activity_type (walking/running/cycling/swimming/strength/sport/other) | duration_min | distance_km (nullable) | steps (nullable) | calories_burned (nullable, user estimate) | source (manual/apple_health/health_connect/wearable) | notes (nullable) |
Manual logging only in Phase 2 (API always writes `source=manual`); the device sources are modeled now so Phase 4 health integrations populate them without a migration.

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
