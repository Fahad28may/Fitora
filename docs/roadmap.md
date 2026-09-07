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
- Dashboard completeness ✅ §4 — now includes today's activity (steps/duration/burn) and today's workout sessions with volume
- Workout progress ✅ §14 — `GET /workouts/progress` (personal records, weekly volume, training frequency) and `/workouts/progress/exercises/{id}` (strength progression), surfaced on the Workout tab
- Backups & disaster recovery ⬜ §60 — not designed
- Email verification / password reset ⬜ §21 — needs an email provider (credential decision)
- Frontend tests ✅ §48 — jest-expo + React Native Testing Library, 35 tests across API-client behaviour, component (BarcodeScanner), screen (Settings), and form validation (register). Wired into CI as a required step
- Accessibility ⬜ §44 — partial; Settings and the barcode scanner have labels, the rest of the app does not
- Offline resilience ⬜ §46 — not started

## Phase 4 — in progress
- Barcode scanning ✅ backend done — `GET /foods/barcode/{barcode}` against Open Food Facts (free, no API key). Crowd-sourced nutrition is validated against plausibility bounds before import, results are cached in the local `foods` table, and the provider is opt-in (`FOOD_DB_PROVIDER`) so no barcode leaves the server by default. Mobile scanner UI ✅ (expo-camera, EAN/UPC only, permission-gated, with a crowd-sourced-data caveat shown before logging)
- Food photo recognition
- Apple Health / Android Health Connect / wearable integrations

## Phase 5
- Advanced analytics
- Deeper personalization
- Additional integrations

Each phase ends with: tests passing, lint/type-check clean, security review of new surface area, docs updated, committed and pushed.
