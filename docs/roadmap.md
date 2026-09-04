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

## Phase 4
- Barcode scanning
- Food photo recognition
- Apple Health / Android Health Connect / wearable integrations

## Phase 5
- Advanced analytics
- Deeper personalization
- Additional integrations

Each phase ends with: tests passing, lint/type-check clean, security review of new surface area, docs updated, committed and pushed.
