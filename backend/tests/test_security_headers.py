import pytest
from httpx import ASGITransport, AsyncClient

from app.core.middleware import MAX_REQUEST_BODY_BYTES
from app.main import app

pytestmark = pytest.mark.asyncio


async def test_security_headers_are_present_on_every_response(
    client: AsyncClient,
) -> None:
    resp = await client.get("/health")

    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "camera=()" in resp.headers["Permissions-Policy"]
    assert "default-src 'none'" in resp.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]


async def test_security_headers_are_present_on_error_responses(
    client: AsyncClient,
) -> None:
    """An unauthenticated 401 is still a response a browser renders."""
    resp = await client.get("/api/v1/dashboard")

    assert resp.status_code == 401
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in resp.headers["Content-Security-Policy"]


async def test_hsts_is_not_sent_over_plain_http(client: AsyncClient) -> None:
    """Sending HSTS over HTTP is meaningless, and sending it in local dev
    would pin localhost to HTTPS in the developer's browser for two years."""
    resp = await client.get("/health")

    assert "Strict-Transport-Security" not in resp.headers


async def test_hsts_is_sent_when_the_request_arrived_over_https() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        resp = await ac.get("/health")

    assert "max-age=" in resp.headers["Strict-Transport-Security"]
    assert "includeSubDomains" in resp.headers["Strict-Transport-Security"]


async def test_hsts_is_sent_when_a_proxy_terminated_tls(client: AsyncClient) -> None:
    """The normal deployment shape: TLS ends at a proxy, which forwards over
    plain HTTP with x-forwarded-proto set."""
    resp = await client.get("/health", headers={"x-forwarded-proto": "https"})

    assert "Strict-Transport-Security" in resp.headers


async def test_oversized_request_is_rejected_before_reaching_the_endpoint(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )

    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"]


async def test_a_lying_content_length_is_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        content=b"{}",
        headers={"Content-Type": "application/json", "Content-Length": "not-a-number"},
    )

    assert resp.status_code == 413


async def test_normal_sized_requests_still_work(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "size-ok@example.com", "password": "correct-horse-battery"},
    )

    assert resp.status_code == 201, resp.text


async def test_rejected_oversized_request_still_carries_security_headers(
    client: AsyncClient,
) -> None:
    """Regression guard for middleware ordering: the headers middleware has to
    sit outside the size limit, or a 413 goes out bare."""
    resp = await client.post(
        "/api/v1/auth/register",
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )

    assert resp.status_code == 413
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
