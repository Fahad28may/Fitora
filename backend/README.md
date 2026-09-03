# Fitora Backend

FastAPI + PostgreSQL API for Fitora.

## Setup

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp ../.env.example ../.env   # then fill in real values
```

Required for local development: a running PostgreSQL instance matching `DATABASE_URL` / `DATABASE_URL_SYNC` in `.env`, and Redis matching `REDIS_URL` (used for rate limiting).

## Run migrations

```bash
alembic upgrade head
```

## Run the API

```bash
uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs` (only enabled when `APP_DEBUG=true`).

## Tests

```bash
pytest
```

Tests run against an isolated in-memory SQLite database via `aiosqlite` — no external services required.

## Lint / type check

```bash
ruff check .
mypy app
```

## Project layout

```text
app/
  main.py              FastAPI app factory, middleware, router registration
  core/                Settings, security (hashing/JWT), rate limiting, logging
  db/                  Async engine/session, declarative base
  models/              SQLAlchemy ORM models
  schemas/             Pydantic request/response models
  repositories/        DB access layer
  services/            Business logic (deterministic calculations, auth logic)
  api/v1/              Route handlers, versioned
alembic/               Migrations
tests/                 pytest suite
```

See [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for the overall system design and [`../docs/ai-safety.md`](../docs/ai-safety.md) for the AI integration boundary once AI features are added.
