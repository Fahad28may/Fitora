import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _register(
    client: AsyncClient,
    email: str = "user@example.com",
    password: str = "correct-horse-battery-staple",
) -> dict:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_register_creates_user_and_returns_tokens(client: AsyncClient) -> None:
    body = await _register(client)
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["email_verified"] is False
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert body["tokens"]["token_type"] == "bearer"


async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    await _register(client)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "another-strong-password"},
    )
    assert resp.status_code == 409


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "short@example.com", "password": "short"}
    )
    assert resp.status_code == 422


async def test_login_with_correct_credentials(client: AsyncClient) -> None:
    await _register(client, email="login@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "correct-horse-battery-staple"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tokens"]["access_token"]


async def test_login_with_wrong_password_is_rejected(client: AsyncClient) -> None:
    await _register(client, email="wrongpw@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "totally-wrong-password"},
    )
    assert resp.status_code == 401


async def test_login_with_unknown_email_is_rejected_generically(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "doesnotexist@example.com", "password": "whatever-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


async def test_me_requires_valid_access_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


async def test_me_returns_current_user_with_valid_token(client: AsyncClient) -> None:
    body = await _register(client, email="me@example.com")
    access_token = body["tokens"]["access_token"]
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


async def test_refresh_rotates_token_and_invalidates_old_one(client: AsyncClient) -> None:
    body = await _register(client, email="refresh@example.com")
    old_refresh = body["tokens"]["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200, resp.text
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != old_refresh

    reuse_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse_resp.status_code == 401


async def test_refresh_with_invalid_token_is_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "bogus-token"})
    assert resp.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    body = await _register(client, email="logout@example.com")
    refresh_token = body["tokens"]["refresh_token"]

    logout_resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204

    reuse_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse_resp.status_code == 401


async def test_cannot_access_another_users_data_with_own_token(client: AsyncClient) -> None:
    user_a = await _register(client, email="a@example.com")
    user_b = await _register(client, email="b@example.com")

    token_a = user_a["tokens"]["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@example.com"
    assert resp.json()["email"] != user_b["user"]["email"]
