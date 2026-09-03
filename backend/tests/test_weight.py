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


async def test_create_and_list_weight_entry(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "weight1@example.com")
    today = date.today().isoformat()

    create_resp = await client.post(
        "/api/v1/weight-entries",
        headers=headers,
        json={"logged_at": today, "weight_kg": 82.5},
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()
    assert body["weight_kg"] == 82.5
    assert body["logged_at"] == today

    list_resp = await client.get("/api/v1/weight-entries", headers=headers)
    assert list_resp.status_code == 200
    entries = list_resp.json()
    assert len(entries) == 1
    assert entries[0]["id"] == body["id"]


async def test_weight_entries_rejects_nonpositive_weight(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "weight-invalid@example.com")
    resp = await client.post(
        "/api/v1/weight-entries",
        headers=headers,
        json={"logged_at": date.today().isoformat(), "weight_kg": 0},
    )
    assert resp.status_code == 422


async def test_list_weight_entries_filters_by_date_range(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "weight-range@example.com")
    today = date.today()

    for offset in (10, 5, 0):
        logged_at = (today - timedelta(days=offset)).isoformat()
        resp = await client.post(
            "/api/v1/weight-entries",
            headers=headers,
            json={"logged_at": logged_at, "weight_kg": 80},
        )
        assert resp.status_code == 201

    resp = await client.get(
        "/api/v1/weight-entries",
        headers=headers,
        params={"from": (today - timedelta(days=6)).isoformat()},
    )
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 2  # offsets 5 and 0, not 10


async def test_list_weight_entries_ordered_most_recent_first(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "weight-order@example.com")
    today = date.today()

    for offset, weight in [(2, 81.0), (0, 79.0), (1, 80.0)]:
        logged_at = (today - timedelta(days=offset)).isoformat()
        await client.post(
            "/api/v1/weight-entries",
            headers=headers,
            json={"logged_at": logged_at, "weight_kg": weight},
        )

    resp = await client.get("/api/v1/weight-entries", headers=headers)
    weights = [entry["weight_kg"] for entry in resp.json()]
    assert weights == [79.0, 80.0, 81.0]


async def test_delete_weight_entry(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "weight-delete@example.com")
    create_resp = await client.post(
        "/api/v1/weight-entries",
        headers=headers,
        json={"logged_at": date.today().isoformat(), "weight_kg": 70},
    )
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/weight-entries/{entry_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/weight-entries", headers=headers)
    assert list_resp.json() == []


async def test_cannot_delete_another_users_weight_entry(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "weight-owner-a@example.com")
    headers_b = await _auth_headers(client, "weight-owner-b@example.com")

    create_resp = await client.post(
        "/api/v1/weight-entries",
        headers=headers_a,
        json={"logged_at": date.today().isoformat(), "weight_kg": 70},
    )
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/weight-entries/{entry_id}", headers=headers_b)
    assert delete_resp.status_code == 404

    still_there = await client.get("/api/v1/weight-entries", headers=headers_a)
    assert len(still_there.json()) == 1


async def test_weight_entries_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/weight-entries")
    assert resp.status_code in (401, 403)


async def test_weight_entries_pagination_limit_enforced(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "weight-pagination@example.com")
    resp = await client.get(
        "/api/v1/weight-entries", headers=headers, params={"limit": 1000}
    )
    assert resp.status_code == 422
