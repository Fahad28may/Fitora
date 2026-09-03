from datetime import date

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_and_list_measurement(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "measure1@example.com")
    resp = await client.post(
        "/api/v1/measurements",
        headers=headers,
        json={"logged_at": date.today().isoformat(), "waist_cm": 80, "chest_cm": 100},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["waist_cm"] == 80
    assert body["hip_cm"] is None

    list_resp = await client.get("/api/v1/measurements", headers=headers)
    assert len(list_resp.json()) == 1


async def test_measurement_requires_at_least_one_field(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "measure-empty@example.com")
    resp = await client.post(
        "/api/v1/measurements",
        headers=headers,
        json={"logged_at": date.today().isoformat()},
    )
    assert resp.status_code == 422


async def test_measurement_rejects_nonpositive_values(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "measure-invalid@example.com")
    resp = await client.post(
        "/api/v1/measurements",
        headers=headers,
        json={"logged_at": date.today().isoformat(), "waist_cm": 0},
    )
    assert resp.status_code == 422


async def test_delete_measurement(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "measure-delete@example.com")
    create_resp = await client.post(
        "/api/v1/measurements",
        headers=headers,
        json={"logged_at": date.today().isoformat(), "arm_cm": 35},
    )
    measurement_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/v1/measurements/{measurement_id}", headers=headers
    )
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/measurements", headers=headers)
    assert list_resp.json() == []


async def test_cannot_delete_another_users_measurement(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "measure-owner-a@example.com")
    headers_b = await _auth_headers(client, "measure-owner-b@example.com")

    create_resp = await client.post(
        "/api/v1/measurements",
        headers=headers_a,
        json={"logged_at": date.today().isoformat(), "leg_cm": 55},
    )
    measurement_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/v1/measurements/{measurement_id}", headers=headers_b
    )
    assert delete_resp.status_code == 404


async def test_measurements_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/measurements")
    assert resp.status_code in (401, 403)
