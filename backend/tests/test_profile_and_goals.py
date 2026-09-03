from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _dob_for_age(age_years: int) -> str:
    today = date.today()
    return (today.replace(year=today.year - age_years) - timedelta(days=1)).isoformat()


async def _register_and_auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_get_profile_before_creation_returns_empty_profile(client: AsyncClient) -> None:
    headers = await _register_and_auth_headers(client, "empty-profile@example.com")
    resp = await client.get("/api/v1/profile", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["sex"] is None
    assert body["height_cm"] is None


async def test_update_profile_persists_fields(client: AsyncClient) -> None:
    headers = await _register_and_auth_headers(client, "profile@example.com")
    resp = await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "display_name": "Test User",
            "date_of_birth": _dob_for_age(30),
            "sex": "female",
            "height_cm": 165,
            "activity_level": "moderate",
            "unit_system": "metric",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["display_name"] == "Test User"
    assert body["sex"] == "female"
    assert body["height_cm"] == 165

    get_resp = await client.get("/api/v1/profile", headers=headers)
    assert get_resp.json()["display_name"] == "Test User"


async def test_update_profile_rejects_underage_date_of_birth(client: AsyncClient) -> None:
    headers = await _register_and_auth_headers(client, "underage@example.com")
    resp = await client.put(
        "/api/v1/profile",
        headers=headers,
        json={"date_of_birth": _dob_for_age(16), "unit_system": "metric"},
    )
    assert resp.status_code == 422


async def test_create_goal_requires_complete_profile_first(client: AsyncClient) -> None:
    headers = await _register_and_auth_headers(client, "no-profile-goal@example.com")
    resp = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "goal_type": "maintain_weight",
            "intensity": "standard",
            "current_weight_kg": 70,
        },
    )
    assert resp.status_code == 400


async def test_create_maintain_goal_succeeds_with_complete_profile(client: AsyncClient) -> None:
    headers = await _register_and_auth_headers(client, "maintain-goal@example.com")
    await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "date_of_birth": _dob_for_age(30),
            "sex": "male",
            "height_cm": 180,
            "activity_level": "moderate",
            "unit_system": "metric",
        },
    )
    resp = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "goal_type": "maintain_weight",
            "intensity": "standard",
            "current_weight_kg": 80,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["target_calories"] > 0
    assert body["is_active"] is True

    active_resp = await client.get("/api/v1/goals/active", headers=headers)
    assert active_resp.status_code == 200
    assert active_resp.json()["id"] == body["id"]


async def test_create_unsafe_goal_without_acknowledgement_is_rejected(
    client: AsyncClient,
) -> None:
    headers = await _register_and_auth_headers(client, "unsafe-goal@example.com")
    await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "date_of_birth": _dob_for_age(25),
            "sex": "female",
            "height_cm": 150,
            "activity_level": "sedentary",
            "unit_system": "metric",
        },
    )
    resp = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "goal_type": "lose_weight",
            "intensity": "aggressive",
            "current_weight_kg": 45,
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["is_safe"] is False
    assert detail["warnings"]


async def test_create_unsafe_goal_with_acknowledgement_succeeds(client: AsyncClient) -> None:
    headers = await _register_and_auth_headers(client, "unsafe-ack-goal@example.com")
    await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "date_of_birth": _dob_for_age(25),
            "sex": "female",
            "height_cm": 150,
            "activity_level": "sedentary",
            "unit_system": "metric",
        },
    )
    resp = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={
            "goal_type": "lose_weight",
            "intensity": "aggressive",
            "current_weight_kg": 45,
            "acknowledge_risk": True,
        },
    )
    assert resp.status_code == 201, resp.text


async def test_creating_new_goal_deactivates_previous_goal(client: AsyncClient) -> None:
    headers = await _register_and_auth_headers(client, "goal-rotation@example.com")
    await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "date_of_birth": _dob_for_age(30),
            "sex": "male",
            "height_cm": 180,
            "activity_level": "moderate",
            "unit_system": "metric",
        },
    )
    first = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={"goal_type": "maintain_weight", "intensity": "standard", "current_weight_kg": 80},
    )
    second = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={"goal_type": "gain_weight", "intensity": "light", "current_weight_kg": 80},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    active_resp = await client.get("/api/v1/goals/active", headers=headers)
    assert active_resp.json()["id"] == second.json()["id"]


async def test_profile_and_goals_require_authentication(client: AsyncClient) -> None:
    profile_resp = await client.get("/api/v1/profile")
    assert profile_resp.status_code in (401, 403)

    goal_resp = await client.post(
        "/api/v1/goals",
        json={"goal_type": "maintain_weight", "intensity": "standard", "current_weight_kg": 70},
    )
    assert goal_resp.status_code in (401, 403)
