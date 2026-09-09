# Fitora Architecture

## 1. Overview

Fitora is split into two deployable units and a shared documentation set:

```text
mobile/   Expo (React Native + TypeScript) client — iOS, Android, and a future web build
backend/  FastAPI (Python) REST API — PostgreSQL primary store, Redis for caching/rate limiting
```

The mobile client never talks to the database, storage, or AI providers directly. Everything goes through the backend, which enforces authentication, authorization, validation, and rate limiting.

```text
Mobile client (Expo/RN/TS)
        │  HTTPS + JWT
        ▼
FastAPI backend  ──────────────►  PostgreSQL (primary data)
        │                          Redis (cache, rate limits, short-lived state)
        ├──► Food database provider (nutrition lookups)
        ├──► AI provider (parsing / coach / vision — server-side only)
        └──► Object storage (photos, private buckets, signed URLs)
```

## 2. Backend architecture

- **Framework**: FastAPI, fully typed, Pydantic v2 models for all request/response validation.
- **Persistence**: PostgreSQL via SQLAlchemy 2.0 (async) + Alembic migrations. No raw SQL string interpolation — parameterized queries / ORM only.
- **Auth**: Argon2id password hashing, short-lived JWT access tokens + rotating refresh tokens, per-endpoint authorization dependency that checks resource ownership (never trusts client-supplied IDs alone).
- **Caching / rate limiting**: Redis, used deliberately (not by default) — login/AI endpoints, food search caching, idempotency keys for offline sync.
- **Layering**: `api/` (routers) → `services/` (business logic) → `repositories/` (DB access) → `models/` (ORM) with `schemas/` (Pydantic) kept separate from ORM models. Deterministic domain logic (BMR/TDEE/macro calculation, trend statistics, the adaptive-target rules) lives in `services/`, is pure and unit-testable, and never depends on the AI provider — the analytics and personalization layers are arithmetic over the user's own logs, not model output.
- **AI boundary**: the LLM is invoked only through a dedicated `ai/` module that (a) sends the minimum necessary structured context, never raw credentials or unrelated PII, (b) requires all mutating actions to go through explicit backend-validated tools (`create_meal`, `log_food`, `create_workout`, `update_weight`, …), and (c) validates all AI output against a schema before it touches the database. See [`docs/ai-safety.md`](docs/ai-safety.md).

## 3. Mobile architecture

- **Framework**: Expo + React Native + TypeScript, structured for an eventual web build without a rewrite.
- **Navigation**: five primary tabs — Home, Nutrition, Workout, Progress, Coach — plus a global "+ Log" quick action (Food, Workout, Water, Weight, Activity).
- **State**: server state via a query/cache layer (e.g. TanStack Query) backed by the FastAPI client; local-only state (draft entries, offline queue) kept separate from server state.
- **Offline**: logging actions write to local pending state first, sync when connectivity returns, using idempotency keys to avoid duplicate entries (see §46 of the master prompt / `docs/data-flow.md`).

## 4. Environments

`development` / `staging` / `production`, each with isolated credentials. Local development never uses production credentials (`.env` is git-ignored; see [`.env.example`](.env.example)).

## 5. Why this stack

- FastAPI + Pydantic gives strong request/response validation "for free," which matters for an app handling health data.
- PostgreSQL's relational model fits the normalized entity graph (User → Meals/Workouts/WeightEntries/Photos/AI conversations) and its constraint system is used actively for data integrity, not just documentation.
- Expo/React Native lets one codebase target iOS, Android, and (later) web, matching the mobile-first requirement without locking out a future web client.

## 6. Non-goals (for now)

- Fitora is not a medical device and does not integrate with clinical systems.
- No server-side rendering / native web app in Phase 1 — mobile first, web deferred.
- No multi-tenant / B2B surface in the initial architecture.
