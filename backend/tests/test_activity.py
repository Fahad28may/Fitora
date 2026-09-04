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


async def test_create_and_list_activity_entry(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act1@example.com")
    today = date.today().isoformat()

    create_resp = await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={
            "logged_at": today,
            "activity_type": "running",
            "duration_min": 30,
            "distance_km": 5.2,
            "calories_burned": 320,
            "notes": "morning run",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()
    assert body["activity_type"] == "running"
    assert body["distance_km"] == 5.2
    # Manual API always records the manual source, never a device source.
    assert body["source"] == "manual"

    list_resp = await client.get("/api/v1/activity-entries", headers=headers)
    assert list_resp.status_code == 200
    entries = list_resp.json()
    assert len(entries) == 1
    assert entries[0]["duration_min"] == 30


async def test_activity_optional_fields_default_to_null(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-optional@example.com")
    resp = await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={
            "logged_at": date.today().isoformat(),
            "activity_type": "walking",
            "duration_min": 15,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["distance_km"] is None
    assert body["steps"] is None
    assert body["calories_burned"] is None
    assert body["notes"] is None


async def test_activity_rejects_nonpositive_duration(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-invalid@example.com")
    resp = await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={"logged_at": date.today().isoformat(), "activity_type": "cycling", "duration_min": 0},
    )
    assert resp.status_code == 422


async def test_activity_rejects_unknown_type(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-type@example.com")
    resp = await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={
            "logged_at": date.today().isoformat(),
            "activity_type": "teleporting",
            "duration_min": 10,
        },
    )
    assert resp.status_code == 422


async def test_activity_entries_scoped_to_requested_day(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-scope@example.com")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={"logged_at": yesterday, "activity_type": "swimming", "duration_min": 45},
    )
    resp = await client.get(
        "/api/v1/activity-entries", headers=headers, params={"date": date.today().isoformat()}
    )
    assert resp.json() == []


async def test_delete_activity_entry(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-delete@example.com")
    create_resp = await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={
            "logged_at": date.today().isoformat(),
            "activity_type": "strength",
            "duration_min": 40,
        },
    )
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/activity-entries/{entry_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/activity-entries", headers=headers)
    assert list_resp.json() == []


async def test_cannot_delete_another_users_activity_entry(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "act-owner-a@example.com")
    headers_b = await _auth_headers(client, "act-owner-b@example.com")
    create_resp = await client.post(
        "/api/v1/activity-entries",
        headers=headers_a,
        json={"logged_at": date.today().isoformat(), "activity_type": "sport", "duration_min": 60},
    )
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/activity-entries/{entry_id}", headers=headers_b)
    assert delete_resp.status_code == 404


async def test_activity_entries_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/activity-entries")
    assert resp.status_code in (401, 403)
