# Roadmap

Priorities, not a schedule. Do not implement a later phase's features before the current phase is stable and tested.

## Phase 1 — Core ✅ done
- Authentication (register/login/refresh/logout, Argon2id, JWT rotation, rate limiting)
- Profile & goals
- Nutrition: food search (manual/custom foods first), food diary logging
- Deterministic calorie/macro calculation (BMR/TDEE)
- Dashboard ("how am I doing today")
- Weight tracking

## Phase 2 — done
- Workouts & exercise tracking ✅
- Progress: measurements ✅, charts ✅ (dependency-free weight + waist trend charts on the mobile Progress screen), photos ✅ backend done — `/progress-photos` upload/list/delete against S3-compatible object storage (MinIO reference provider), private bucket + presigned URLs + magic-byte/size validation; disabled→503 when unconfigured, like AI. Requires a provisioned bucket + `S3_*` env to run live; mobile UI is a follow-up
- Water logging ✅
- Activity tracking (architecture only — real integrations in Phase 4) ✅ backend architecture done: `ActivityEntry` model + `/activity-entries` CRUD, manual logging only. `ActivitySource` already models the future `apple_health`/`health_connect`/`wearable` sources so Phase 4 device sync needs no migration. Mobile UI + device integrations deferred to Phase 4.

## Phase 3 — in progress
- AI natural-language food parsing ✅ (`POST /ai/parse-food`, OpenRouter)
- AI fitness coach ✅ (`POST /ai/coach/messages`, read-only/advisory — no tool-calling yet, see `docs/ai-safety.md`)
- Personalized recommendations ✅ (`GET /recommendations`, deterministic/rule-based — no LLM, works with AI disabled; surfaced as "Insights" on the mobile home screen)
- Mobile UI for AI food parsing + coach ✅ (Coach chat tab and natural-language food logging wired into the mobile app)
- AI tool-calling for mutating actions ✅ built as a propose→confirm flow (`POST /ai/actions/propose`, `POST /ai/actions/confirm`) for `log_weight`/`log_water`/`log_food` — the model only proposes, the deterministic confirm step writes with `user_id` from the session and re-validated bounds (see `docs/ai-safety.md`). `create_workout`/`create_meal` and a mobile UI for this flow are follow-ups. The coach itself still cannot write data.

## Cross-cutting (spec sections not tied to a phase)
- User data rights ✅ §29 — `GET /account/export`, `DELETE /account`, surfaced as Settings → Privacy in the app
- Consent ✅ §30 — append-only `consent_records`, nothing pre-selected, switches with plain-language copy
- Audit logging ✅ §61 — `audit_events` for register/login/logout/consent/export/deletion; `GET /account/security-events` lets a user read their own
- Security headers + request size limit ✅ §59
- Custom meals ✅ §5 — `meals`/`meal_items`, `POST /meals/{id}/log` expands a template into ordinary diary entries; mobile builds a meal from what's already logged for a category
- Charts ✅ §16 — all six the spec names: weight and waist (existing), plus calories, protein and activity from `GET /dashboard/history`, and weekly workout volume + per-exercise strength from the workout-progress endpoints
- Dashboard completeness ✅ §4 — now includes today's activity (steps/duration/burn) and today's workout sessions with volume
- Workout progress ✅ §14 — `GET /workouts/progress` (personal records, weekly volume, training frequency) and `/workouts/progress/exercises/{id}` (strength progression), surfaced on the Workout tab
- Backups & disaster recovery ◐ §60 — designed in `docs/backups-and-recovery.md`; **not implemented**, blocked on hosting/database provider selection. No restoration has been tested
- Email verification / password reset ⬜ §21 — needs an email provider (credential decision)
- Frontend tests ✅ §48 — jest-expo + React Native Testing Library, 140 tests across API-client behaviour, the health-sync layer, components (BarcodeScanner, HealthSyncCard), screens (Settings, Log activity, Analytics), and form validation (register). Wired into CI as a required step
- Accessibility ✅ §44 — every interactive element across the app has an accessible name, selection state is exposed via `accessibilityState` rather than colour alone, and recommendation priority now carries a text label as well as a coloured rule. A static test fails the build if a new control ships without a name. Contrast and reduced-motion review still outstanding
- Offline resilience ✅ §46 — server-side replay protection via an optional `Idempotency-Key` header on the logging endpoints (food diary, water, weight, activity), plus a client outbox that queues writes when the network is down, replays them with the key they were queued with, and shows a pending-sync count on Home. Wired to water quick-add and activity logging; the other logging screens are a follow-up

## Phase 4 — in progress
- Barcode scanning ✅ backend done — `GET /foods/barcode/{barcode}` against Open Food Facts (free, no API key). Crowd-sourced nutrition is validated against plausibility bounds before import, results are cached in the local `foods` table, and the provider is opt-in (`FOOD_DB_PROVIDER`) so no barcode leaves the server by default. Mobile scanner UI ✅ (expo-camera, EAN/UPC only, permission-gated, with a crowd-sourced-data caveat shown before logging)
- Food photo recognition ✅ §7/§8 — `POST /ai/recognize-food` against a free OpenRouter vision model (`minimax/minimax-m3:free`, live-verified). Calories are always a range, never an exact number, and an overconfident range is widened server-side rather than trusted. The image is processed in memory and never stored. Opt-in via `AI_MODEL_VISION`; camera + library capture on the Nutrition tab
- Mobile activity logging ✅ — `src/api/activity.ts` plus a `Log activity` screen off the Home Activity card (type, minutes, optional distance/steps/calories, delete). Routed through the outbox like water, and every entry shows whether it was typed or device-reported. The backend has accepted activity since Phase 2; until now the app had no client for it at all
- Apple Health / Android Health Connect / wearable integrations ◐ **everything except the native read is built**. Server: `POST /activity-entries/sync` — consent-gated on `wearable_access`, idempotent by the device's `external_id`, bounds-checked exactly like manual entries, labelled with its real source. Client: a `HealthProvider` seam, the sync orchestrator (consent-before-OS-permission, 30-day first window, 1-day overlap re-read, paging at 500, client-side bounds filtering so one bad record can't 422 a batch), and a Settings card that says plainly when a build can't read a health app instead of showing a dead Connect button — 33 tests against a fake provider, including guards for the two detectable ways a provider can get `external_id` wrong (colliding ids in one read, and ids that change between overlap re-reads). What remains is one file implementing `HealthProvider` against HealthKit / Health Connect, which needs a custom development build and, for iOS, an Apple Developer account. `docs/health-integrations.md` is a step-by-step runbook for it: prerequisites, the exact scopes and config, a provider sketch, and a nine-check on-device verification list

## Phase 5 — in progress
- Advanced analytics ✅ — `GET /analytics/summary`, surfaced as an Analytics screen off the Progress tab. Smoothed weight trend plus a least-squares rate of change, goal projection, logging streaks, days-on-target, macro split, weekday patterns, and an intake-vs-expenditure balance. Deterministic, no AI. The design constraint is §16's "avoid misleading charts or fake precision", so each block refuses rather than guesses: no rate below 4 weigh-ins over 14 days, no projection when the trend moves away from the goal or runs past two years, adherence reported as "n of m" instead of a percentage, and reported activity burn shown but never added to the estimate (the activity multiplier already counts exercise)
- Deeper personalization ✅ — `GET /analytics/adaptive-targets`. Re-estimates the user's *observed* maintenance calories from their own intake and weight trend (`intake − change × 7700 ÷ days`) rather than the Mifflin-St Jeor prediction, and proposes a target from it. Advisory only: it never writes a goal, is clamped to the 1200 kcal/day floor and to a 20% move per step, and is withheld entirely when the estimate is physiologically implausible or more than 40% from the profile prediction — that pattern means under-logging, not an unusual metabolism
- Additional integrations ✅ — Open Food Facts name search (`GET /foods/search?include_external=true`), extending the barcode-only integration. Two gates, not one: the operator enables the provider, and the user opts in per search, because a search term is free text they typed rather than a barcode they pointed a camera at. Same plausibility validation and local caching as the barcode path; unusable results are skipped individually; a provider outage degrades the search to local-only
- Still open: device-side Apple Health / Health Connect read (Phase 4, see `docs/health-integrations.md`), backups (`docs/backups-and-recovery.md`), and email verification / password reset — all blocked on decisions outside the code

Each phase ends with: tests passing, lint/type-check clean, security review of new surface area, docs updated, committed and pushed.
