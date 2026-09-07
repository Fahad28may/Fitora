from datetime import date

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TODAY = date.today().isoformat()


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _grant_wearable_consent(client: AsyncClient, headers: dict[str, str]) -> None:
    resp = await client.put(
        "/api/v1/account/consents",
        headers=headers,
        json={"consent_type": "wearable_access", "granted": True},
    )
    assert resp.status_code == 200, resp.text


def _entry(external_id: str = "hk-1", **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "external_id": external_id,
        "logged_at": TODAY,
        "activity_type": "running",
        "duration_min": 30,
        "distance_km": 5.0,
        "steps": 6000,
        "calories_burned": 320,
    }
    base.update(overrides)
    return base


async def _sync(
    client: AsyncClient,
    headers: dict[str, str],
    entries: list[dict[str, object]],
    source: str = "apple_health",
):
    return await client.post(
        "/api/v1/activity-entries/sync",
        headers=headers,
        json={"source": source, "entries": entries},
    )


# --- consent gate (§30) ---------------------------------------------------


async def test_sync_is_refused_without_wearable_consent(client: AsyncClient) -> None:
    """§30: consent before accessing health/wearable data. The device's OS
    permission is the device agreeing to hand data over; this is the user
    agreeing Fitora may store it."""
    headers = await _auth_headers(client, "sync-noconsent@example.com")

    resp = await _sync(client, headers, [_entry()])

    assert resp.status_code == 403
    assert "Settings" in resp.json()["detail"]

    listed = await client.get(
        "/api/v1/activity-entries", headers=headers, params={"date": TODAY}
    )
    assert listed.json() == []


async def test_withdrawing_consent_stops_future_syncs(client: AsyncClient) -> None:
    """Consent has to be revocable in a way that actually takes effect."""
    headers = await _auth_headers(client, "sync-revoke@example.com")
    await _grant_wearable_consent(client, headers)
    assert (await _sync(client, headers, [_entry("hk-1")])).status_code == 200

    await client.put(
        "/api/v1/account/consents",
        headers=headers,
        json={"consent_type": "wearable_access", "granted": False},
    )

    resp = await _sync(client, headers, [_entry("hk-2")])
    assert resp.status_code == 403


# --- idempotency ----------------------------------------------------------


async def test_resyncing_the_same_window_does_not_duplicate(
    client: AsyncClient,
) -> None:
    """A health app re-reports the same workout on every sync. That's the
    normal case, not the exception — syncing twice must be a no-op."""
    headers = await _auth_headers(client, "sync-idem@example.com")
    await _grant_wearable_consent(client, headers)
    entries = [_entry("hk-1"), _entry("hk-2", activity_type="cycling")]

    first = await _sync(client, headers, entries)
    second = await _sync(client, headers, entries)

    assert first.json() == {
        "source": "apple_health",
        "received": 2,
        "created": 2,
        "updated": 0,
    }
    assert second.json()["created"] == 0
    assert second.json()["updated"] == 2

    listed = await client.get(
        "/api/v1/activity-entries", headers=headers, params={"date": TODAY}
    )
    assert len(listed.json()) == 2


async def test_a_revised_record_updates_in_place(client: AsyncClient) -> None:
    """Devices revise records after the fact — a run gets its final distance
    once processing finishes."""
    headers = await _auth_headers(client, "sync-revise@example.com")
    await _grant_wearable_consent(client, headers)
    await _sync(client, headers, [_entry("hk-1", duration_min=30, distance_km=5.0)])

    await _sync(client, headers, [_entry("hk-1", duration_min=32, distance_km=5.4)])

    listed = (
        await client.get(
            "/api/v1/activity-entries", headers=headers, params={"date": TODAY}
        )
    ).json()
    assert len(listed) == 1
    assert listed[0]["duration_min"] == 32
    assert listed[0]["distance_km"] == 5.4


async def test_the_same_external_id_from_different_sources_is_not_a_collision(
    client: AsyncClient,
) -> None:
    """Two devices can each call their record "1"."""
    headers = await _auth_headers(client, "sync-sources@example.com")
    await _grant_wearable_consent(client, headers)

    await _sync(client, headers, [_entry("1")], source="apple_health")
    await _sync(client, headers, [_entry("1")], source="health_connect")

    listed = await client.get(
        "/api/v1/activity-entries", headers=headers, params={"date": TODAY}
    )
    assert len(listed.json()) == 2


async def test_manual_entries_are_untouched_by_sync(client: AsyncClient) -> None:
    """Manual entries have no external_id, so the dedup constraint must not
    catch them — a user can log the same walk twice by hand if they mean to."""
    headers = await _auth_headers(client, "sync-manual@example.com")
    await _grant_wearable_consent(client, headers)
    for _ in range(2):
        resp = await client.post(
            "/api/v1/activity-entries",
            headers=headers,
            json={"logged_at": TODAY, "activity_type": "walking", "duration_min": 20},
        )
        assert resp.status_code == 201, resp.text

    await _sync(client, headers, [_entry("hk-1")])

    listed = (
        await client.get(
            "/api/v1/activity-entries", headers=headers, params={"date": TODAY}
        )
    ).json()
    assert len(listed) == 3
    assert sum(1 for e in listed if e["source"] == "manual") == 2


# --- provenance -----------------------------------------------------------


async def test_synced_entries_are_labelled_with_their_device_source(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "sync-source-label@example.com")
    await _grant_wearable_consent(client, headers)

    await _sync(client, headers, [_entry()], source="health_connect")

    listed = (
        await client.get(
            "/api/v1/activity-entries", headers=headers, params={"date": TODAY}
        )
    ).json()
    assert listed[0]["source"] == "health_connect"


async def test_a_sync_cannot_claim_entries_were_manual(client: AsyncClient) -> None:
    """"The user typed this" and "a device reported this" are different
    claims; a sync must not be able to make the first one."""
    headers = await _auth_headers(client, "sync-notmanual@example.com")
    await _grant_wearable_consent(client, headers)

    resp = await _sync(client, headers, [_entry()], source="manual")

    assert resp.status_code == 422


# --- validation -----------------------------------------------------------


async def test_device_data_is_bounds_checked_like_manual_data(
    client: AsyncClient,
) -> None:
    """A health app reporting a 40-hour run is a bug somewhere. Device data
    is not more trustworthy than typed data."""
    headers = await _auth_headers(client, "sync-bounds@example.com")
    await _grant_wearable_consent(client, headers)

    resp = await _sync(client, headers, [_entry(duration_min=2400)])

    assert resp.status_code == 422


async def test_an_empty_sync_is_rejected(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "sync-empty@example.com")
    await _grant_wearable_consent(client, headers)

    resp = await _sync(client, headers, [])

    assert resp.status_code == 422


async def test_an_oversized_batch_is_rejected(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "sync-huge@example.com")
    await _grant_wearable_consent(client, headers)

    resp = await _sync(client, headers, [_entry(f"hk-{i}") for i in range(600)])

    assert resp.status_code == 422


async def test_sync_is_scoped_to_the_caller(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "sync-scope-a@example.com")
    headers_b = await _auth_headers(client, "sync-scope-b@example.com")
    await _grant_wearable_consent(client, headers_a)
    await _grant_wearable_consent(client, headers_b)

    await _sync(client, headers_a, [_entry("hk-1")])
    # Same external id, different user — must create, not collide.
    resp = await _sync(client, headers_b, [_entry("hk-1")])

    assert resp.json()["created"] == 1
    listed_b = await client.get(
        "/api/v1/activity-entries", headers=headers_b, params={"date": TODAY}
    )
    assert len(listed_b.json()) == 1


async def test_sync_requires_authentication(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/activity-entries/sync",
        json={"source": "apple_health", "entries": [_entry()]},
    )

    assert resp.status_code == 401


async def test_synced_activity_reaches_the_dashboard(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "sync-dashboard@example.com")
    await _grant_wearable_consent(client, headers)

    await _sync(client, headers, [_entry(duration_min=45, steps=8000)])

    activity = (await client.get("/api/v1/dashboard", headers=headers)).json()["activity"]
    assert activity["duration_min"] == 45
    assert activity["steps"] == 8000
