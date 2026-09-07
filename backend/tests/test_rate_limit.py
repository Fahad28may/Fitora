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


async def test_limiter_buckets_clients_separately_behind_a_proxy() -> None:
    """The real bug: with slowapi's get_remote_address, every request behind a
    proxy carries the proxy's IP, so all users share one bucket and one
    abusive client locks out everyone. Keyed on the forwarded address, two
    clients get two buckets.
    """
    from app.core.client_ip import resolve_client_ip

    def key(request: Request) -> str:
        return resolve_client_ip(request, trusted_proxy_count=1)

    limiter = Limiter(key_func=key)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.post("/limited")
    @limiter.limit("2/minute")
    async def limited_endpoint(request: Request) -> dict[str, bool]:
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        noisy = [
            (await ac.post("/limited", headers={"X-Forwarded-For": "203.0.113.1"})).status_code
            for _ in range(4)
        ]
        # A different client, after the first one is already exhausted.
        quiet = (
            await ac.post("/limited", headers={"X-Forwarded-For": "203.0.113.2"})
        ).status_code

    assert 429 in noisy[2:], f"noisy client should be limited, got {noisy}"
    assert quiet == 200, "a different client must not inherit someone else's limit"


async def test_a_spoofed_forwarded_header_cannot_evade_the_limiter() -> None:
    """Counting from the right of the chain is what makes trusting the header
    safe: a caller prepending a fresh fake IP per request still lands in their
    own real bucket."""
    from app.core.client_ip import resolve_client_ip

    def key(request: Request) -> str:
        return resolve_client_ip(request, trusted_proxy_count=1)

    limiter = Limiter(key_func=key)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.post("/limited")
    @limiter.limit("2/minute")
    async def limited_endpoint(request: Request) -> dict[str, bool]:
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        statuses = []
        for attempt in range(4):
            # A new spoofed prefix each time; the proxy appends the real IP.
            forwarded = f"9.9.9.{attempt}, 203.0.113.9"
            statuses.append(
                (await ac.post("/limited", headers={"X-Forwarded-For": forwarded})).status_code
            )

    assert 429 in statuses[2:], f"spoofing must not reset the bucket, got {statuses}"


def test_storage_uri_is_memory_when_redis_is_not_configured() -> None:
    from app.core.config import Settings

    settings = Settings(REDIS_URL="")  # type: ignore[call-arg]

    assert settings.rate_limit_storage_uri == "memory://"
    assert settings.rate_limiting_is_shared is False


def test_storage_uri_uses_redis_when_configured() -> None:
    """In-memory counters are per-process, so a multi-instance deployment
    multiplies every limit by its instance count."""
    from app.core.config import Settings

    settings = Settings(REDIS_URL="redis://cache:6379/0")  # type: ignore[call-arg]

    assert settings.rate_limit_storage_uri == "redis://cache:6379/0"
    assert settings.rate_limiting_is_shared is True


def test_the_app_limiter_does_not_use_the_proxy_blind_key_function() -> None:
    """Regression guard: slowapi's get_remote_address is the default and the
    obvious thing to reach for, and it is exactly what broke this."""
    from slowapi.util import get_remote_address

    from app.core.client_ip import client_ip_key
    from app.core.rate_limit import limiter

    assert limiter._key_func is not get_remote_address
    assert limiter._key_func is client_ip_key


async def test_an_unreachable_redis_degrades_instead_of_500ing_every_route() -> None:
    """Found while verifying the Redis change: without in-memory fallback, a
    storage error escapes and every rate-limited route — i.e. the whole API —
    returns 500. A Redis blip taking the service down is a far worse failure
    than the per-instance counters shared storage exists to fix.

    Correct behaviour is to degrade to in-memory limiting: some brute-force
    protection rather than none, and exactly what we had before Redis.
    """
    limiter = Limiter(
        key_func=get_remote_address,
        # Port chosen to be closed.
        storage_uri="redis://127.0.0.1:6399/0",
        in_memory_fallback_enabled=True,
    )
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

    assert 500 not in statuses, f"a dead Redis must not 500 the route, got {statuses}"
    assert statuses[:2] == [200, 200]
    # Still limiting, just locally.
    assert 429 in statuses[2:], f"fallback must keep limiting, got {statuses}"


async def test_the_health_endpoint_is_exempt_from_rate_limiting() -> None:
    """Load balancers poll this constantly. A health check that 429s under its
    own monitoring reports a healthy service as down."""
    from app.main import app as fitora_app

    transport = ASGITransport(app=fitora_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        statuses = [(await ac.get("/health")).status_code for _ in range(30)]

    assert set(statuses) == {200}, f"health should never be limited, got {set(statuses)}"
