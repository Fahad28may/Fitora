import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("RATE_LIMIT_LOGIN_PER_MINUTE", "1000")
os.environ.setdefault("RATE_LIMIT_DEFAULT_PER_MINUTE", "1000")
# AI limiter buckets are per-IP and process-global; all tests share one IP, so
# without a high ceiling the AI endpoints' 20/hour default would couple tests
# together and flake once enough AI calls accumulate across the session.
os.environ.setdefault("RATE_LIMIT_AI_PER_HOUR", "10000")
# Force-disabled (not setdefault) regardless of what a developer's local
# .env has: pydantic-settings' env_file loading would otherwise leak a real
# AI_API_KEY into the test run, silently turning "AI disabled" tests into
# real, quota-consuming calls to the actual provider.
os.environ["AI_API_KEY"] = ""
os.environ.setdefault("RATE_LIMIT_BARCODE_PER_HOUR", "10000")
os.environ.setdefault("RATE_LIMIT_ACCOUNT_PER_HOUR", "10000")
# Same reasoning as AI_API_KEY above: a developer with FOOD_DB_PROVIDER set in
# their .env would otherwise turn the "barcode lookup disabled" test into a
# real request to Open Food Facts.
os.environ["FOOD_DB_PROVIDER"] = ""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.seed_data import SEED_EXERCISES
from app.db.session import get_db

# Imported eagerly at module load, before any event loop exists, so
# module-level side effects (Argon2 hasher init, engine creation, route
# registration) happen at plain synchronous import time rather than racing
# SQLAlchemy's greenlet bridge inside the first test.
from app.main import app
from app.models.exercise import Exercise


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    db_file = Path(tempfile.gettempdir()) / f"fitora_test_{os.urandom(8).hex()}.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # First execute() on a freshly created async engine occasionally races
        # SQLAlchemy's greenlet bridge on Python 3.14 (the DDL above is a
        # run_sync, not an execute); force a real execute() to happen while
        # still inside this transactional context, before any test runs.
        await conn.execute(text("SELECT 1"))

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add_all(
            Exercise(
                name=row[0],
                muscle_groups=row[1],
                equipment=row[2],
                instructions=row[3],
                difficulty=row[4],
                exercise_type=row[5],
            )
            for row in SEED_EXERCISES
        )
        await session.commit()
        yield session

    await engine.dispose()
    db_file.unlink(missing_ok=True)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _get_db_override() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()
