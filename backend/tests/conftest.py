import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("RATE_LIMIT_LOGIN_PER_MINUTE", "1000")
os.environ.setdefault("RATE_LIMIT_DEFAULT_PER_MINUTE", "1000")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db

# Imported eagerly at module load, before any event loop exists, so
# module-level side effects (Argon2 hasher init, engine creation, route
# registration) happen at plain synchronous import time rather than racing
# SQLAlchemy's greenlet bridge inside the first test.
from app.main import app


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
