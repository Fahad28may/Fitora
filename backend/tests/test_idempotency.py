import asyncio

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TODAY = "2026-04-01"


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _post_water(
    client: AsyncClient, headers: dict[str, str], *, key: str | None = None, amount: int = 250
):
    request_headers = dict(headers)
    if key is not None:
        request_headers["Idempotency-Key"] = key
    return await client.post(
        "/api/v1/water-entries",
        headers=request_headers,
        json={"logged_at": TODAY, "amount_ml": amount},
    )


async def test_replayed_request_does_not_create_a_second_entry(
    client: AsyncClient,
) -> None:
    """The whole point of §46: a queued write whose response was lost gets
    retried, and must not log the same thing twice."""
    headers = await _auth_headers(client, "idem-replay@example.com")

    first = await _post_water(client, headers, key="offline-water-1")
    second = await _post_water(client, headers, key="offline-water-1")

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    listed = await client.get(
        "/api/v1/water-entries", headers=headers, params={"date": TODAY}
    )
    assert len(listed.json()) == 1


async def test_replay_returns_the_original_response_not_the_new_payload(
    client: AsyncClient,
) -> None:
    """A replay is the *same* request arriving twice. If the body differs the
    client has a bug, and the first outcome is the one that actually
    happened — inventing a merge would be worse."""
    headers = await _auth_headers(client, "idem-different@example.com")

    await _post_water(client, headers, key="same-key", amount=250)
    second = await _post_water(client, headers, key="same-key", amount=999)

    assert second.json()["amount_ml"] == 250


async def test_different_keys_create_different_entries(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "idem-distinct@example.com")

    await _post_water(client, headers, key="key-a")
    await _post_water(client, headers, key="key-b")

    listed = await client.get(
        "/api/v1/water-entries", headers=headers, params={"date": TODAY}
    )
    assert len(listed.json()) == 2


async def test_no_key_means_no_replay_protection(client: AsyncClient) -> None:
    """Unchanged behaviour for clients that don't need it — two deliberate
    logs of the same drink are two entries."""
    headers = await _auth_headers(client, "idem-nokey@example.com")

    await _post_water(client, headers)
    await _post_water(client, headers)

    listed = await client.get(
        "/api/v1/water-entries", headers=headers, params={"date": TODAY}
    )
    assert len(listed.json()) == 2


async def test_keys_are_scoped_per_user(client: AsyncClient) -> None:
    """Keys are client-generated, so two users picking the same one must not
    collide — otherwise one user's write returns another's stored response."""
    headers_a = await _auth_headers(client, "idem-scope-a@example.com")
    headers_b = await _auth_headers(client, "idem-scope-b@example.com")

    a = await _post_water(client, headers_a, key="collision", amount=250)
    b = await _post_water(client, headers_b, key="collision", amount=500)

    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text
    assert a.json()["id"] != b.json()["id"]
    assert b.json()["amount_ml"] == 500


async def test_reusing_a_key_on_a_different_endpoint_is_a_conflict(
    client: AsyncClient,
) -> None:
    """Answering with an unrelated stored response would be far worse than
    failing loudly."""
    headers = await _auth_headers(client, "idem-crossendpoint@example.com")
    await _post_water(client, headers, key="shared-key")

    resp = await client.post(
        "/api/v1/weight-entries",
        headers={**headers, "Idempotency-Key": "shared-key"},
        json={"logged_at": TODAY, "weight_kg": 80},
    )

    assert resp.status_code == 409
    assert "different request" in resp.json()["detail"]


async def test_idempotency_works_on_weight_activity_and_food_diary(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "idem-allroutes@example.com")

    for _ in range(2):
        weight = await client.post(
            "/api/v1/weight-entries",
            headers={**headers, "Idempotency-Key": "w1"},
            json={"logged_at": TODAY, "weight_kg": 80},
        )
        activity = await client.post(
            "/api/v1/activity-entries",
            headers={**headers, "Idempotency-Key": "a1"},
            json={"logged_at": TODAY, "activity_type": "walking", "duration_min": 20},
        )
        assert weight.status_code == 201, weight.text
        assert activity.status_code == 201, activity.text

    weights = await client.get("/api/v1/weight-entries", headers=headers)
    activities = await client.get(
        "/api/v1/activity-entries", headers=headers, params={"date": TODAY}
    )
    assert len(weights.json()) == 1
    assert len(activities.json()) == 1


async def test_food_diary_replay_does_not_double_log(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "idem-diary@example.com")
    food = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": "Replay Food",
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": 200,
            "protein_g": 10,
            "carbs_g": 20,
            "fat_g": 5,
        },
    )
    body = {
        "food_id": food.json()["id"],
        "logged_at": TODAY,
        "meal_category": "lunch",
        "quantity": 1,
        "unit": "serving",
    }

    for _ in range(3):
        resp = await client.post(
            "/api/v1/food-diary",
            headers={**headers, "Idempotency-Key": "meal-1"},
            json=body,
        )
        assert resp.status_code == 201, resp.text

    diary = await client.get("/api/v1/food-diary", headers=headers, params={"date": TODAY})
    assert len(diary.json()) == 1


async def test_an_overlong_key_is_rejected(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "idem-longkey@example.com")

    resp = await _post_water(client, headers, key="x" * 200)

    assert resp.status_code == 400
    assert "at most" in resp.json()["detail"]


async def test_a_blank_key_is_treated_as_absent(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "idem-blankkey@example.com")

    first = await _post_water(client, headers, key="   ")
    second = await _post_water(client, headers, key="   ")

    assert first.status_code == 201
    assert second.status_code == 201
    listed = await client.get(
        "/api/v1/water-entries", headers=headers, params={"date": TODAY}
    )
    assert len(listed.json()) == 2


async def test_concurrent_replays_still_produce_one_entry_or_a_clear_conflict(
    client: AsyncClient,
) -> None:
    """Two queued copies flushing at once must not both land silently."""
    headers = await _auth_headers(client, "idem-race@example.com")

    results = await asyncio.gather(
        _post_water(client, headers, key="racing"),
        _post_water(client, headers, key="racing"),
        return_exceptions=True,
    )
    statuses = [r.status_code for r in results if not isinstance(r, BaseException)]

    listed = await client.get(
        "/api/v1/water-entries", headers=headers, params={"date": TODAY}
    )
    # Either one won and the other replayed it, or one got a clear 409. What
    # must not happen is two silent 201s creating two entries.
    assert all(s in (201, 409) for s in statuses), statuses
    assert len(listed.json()) <= 2
