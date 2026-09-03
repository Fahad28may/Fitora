import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

pytestmark = pytest.mark.asyncio


async def test_slowapi_limiter_returns_429_once_limit_is_exceeded() -> None:
    """Exercises the exact rate-limiting mechanism used on /auth/login and
    /auth/register (slowapi Limiter + per-route decorator + exception
    handler), against a minimal app, so the limit is deterministic and
    isolated from other tests' request volume.
    """
    limiter = Limiter(key_func=get_remote_address)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.post("/limited")
    @limiter.limit("2/minute")
    async def limited_endpoint(request: Request) -> dict[str, bool]:
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        statuses = [(await ac.post("/limited")).status_code for _ in range(4)]

    assert statuses[:2] == [200, 200]
    assert 429 in statuses[2:], f"Expected a 429 after exceeding the limit, got {statuses}"
