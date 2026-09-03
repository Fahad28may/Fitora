# Roadmap

Priorities, not a schedule. Do not implement a later phase's features before the current phase is stable and tested.

## Phase 1 — Core (current)
- Authentication (register/login/refresh/logout, Argon2id, JWT rotation, rate limiting)
- Profile & goals
- Nutrition: food search (manual/custom foods first), food diary logging
- Deterministic calorie/macro calculation (BMR/TDEE)
- Dashboard ("how am I doing today")
- Weight tracking

## Phase 2
- Workouts & exercise tracking
- Progress (measurements, photos, charts)
- Water logging
- Activity tracking (architecture only — real integrations in Phase 4)

## Phase 3
- AI natural-language food parsing
- AI fitness coach
- Personalized recommendations

## Phase 4
- Barcode scanning
- Food photo recognition
- Apple Health / Android Health Connect / wearable integrations

## Phase 5
- Advanced analytics
- Deeper personalization
- Additional integrations

Each phase ends with: tests passing, lint/type-check clean, security review of new surface area, docs updated, committed and pushed.
