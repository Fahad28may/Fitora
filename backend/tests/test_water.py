from datetime import date, timedelta

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


async def test_create_and_list_water_entry_defaults_to_today(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "water1@example.com")
    today = date.today().isoformat()

    create_resp = await client.post(
        "/api/v1/water-entries", headers=headers, json={"logged_at": today, "amount_ml": 250}
    )
    assert create_resp.status_code == 201, create_resp.text

    list_resp = await client.get("/api/v1/water-entries", headers=headers)
    assert list_resp.status_code == 200
    entries = list_resp.json()
    assert len(entries) == 1
    assert entries[0]["amount_ml"] == 250


async def test_water_entries_rejects_nonpositive_amount(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "water-invalid@example.com")
    resp = await client.post(
        "/api/v1/water-entries",
        headers=headers,
        json={"logged_at": date.today().isoformat(), "amount_ml": 0},
    )
    assert resp.status_code == 422


async def test_water_entries_scoped_to_requested_day(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "water-scope@example.com")
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    await client.post(
        "/api/v1/water-entries", headers=headers, json={"logged_at": yesterday, "amount_ml": 500}
    )

    resp = await client.get(
        "/api/v1/water-entries", headers=headers, params={"date": date.today().isoformat()}
    )
    assert resp.json() == []


async def test_delete_water_entry(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "water-delete@example.com")
    create_resp = await client.post(
        "/api/v1/water-entries",
        headers=headers,
        json={"logged_at": date.today().isoformat(), "amount_ml": 300},
    )
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/water-entries/{entry_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/water-entries", headers=headers)
    assert list_resp.json() == []


async def test_cannot_delete_another_users_water_entry(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "water-owner-a@example.com")
    headers_b = await _auth_headers(client, "water-owner-b@example.com")

    create_resp = await client.post(
        "/api/v1/water-entries",
        headers=headers_a,
        json={"logged_at": date.today().isoformat(), "amount_ml": 300},
    )
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/water-entries/{entry_id}", headers=headers_b)
    assert delete_resp.status_code == 404


async def test_water_entries_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/water-entries")
    assert resp.status_code in (401, 403)


async def test_dashboard_sums_todays_water_entries(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "water-dashboard@example.com")
    today = date.today().isoformat()

    await client.post(
        "/api/v1/water-entries", headers=headers, json={"logged_at": today, "amount_ml": 250}
    )
    await client.post(
        "/api/v1/water-entries", headers=headers, json={"logged_at": today, "amount_ml": 300}
    )

    resp = await client.get("/api/v1/dashboard", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["water"]["consumed_ml"] == 550
    assert resp.json()["water"]["target_ml"] is None
