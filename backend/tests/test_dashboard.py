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


async def test_dashboard_with_no_data_shows_zeros_and_no_targets(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "dash-empty@example.com")
    resp = await client.get("/api/v1/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_profile"] is False
    assert body["has_active_goal"] is False
    assert body["calories"]["target"] is None
    assert body["calories"]["consumed"] == 0
    assert body["latest_weight_kg"] is None


async def test_dashboard_defaults_to_today(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "dash-today@example.com")
    resp = await client.get("/api/v1/dashboard", headers=headers)
    assert resp.json()["date"] == date.today().isoformat()


async def test_dashboard_reflects_active_goal_targets(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "dash-goal@example.com")
    await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "date_of_birth": (date.today().replace(year=date.today().year - 30)).isoformat(),
            "sex": "male",
            "height_cm": 180,
            "activity_level": "moderate",
            "unit_system": "metric",
        },
    )
    goal_resp = await client.post(
        "/api/v1/goals",
        headers=headers,
        json={"goal_type": "maintain_weight", "intensity": "standard", "current_weight_kg": 80},
    )
    assert goal_resp.status_code == 201

    resp = await client.get("/api/v1/dashboard", headers=headers)
    body = resp.json()
    assert body["has_active_goal"] is True
    assert body["calories"]["target"] == goal_resp.json()["target_calories"]
    assert body["calories"]["remaining"] == body["calories"]["target"]


async def test_dashboard_sums_todays_food_diary_entries(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "dash-food@example.com")
    food_resp = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": "Rice",
            "serving_description": "1 cup",
            "serving_grams": 150,
            "calories_kcal": 200,
            "protein_g": 4,
            "carbs_g": 45,
            "fat_g": 1,
        },
    )
    food_id = food_resp.json()["id"]
    today = date.today().isoformat()

    await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food_id,
            "logged_at": today,
            "meal_category": "lunch",
            "quantity": 2,
            "unit": "serving",
        },
    )

    resp = await client.get("/api/v1/dashboard", headers=headers)
    body = resp.json()
    assert body["calories"]["consumed"] == 400
    assert body["protein"]["consumed_g"] == 8
    assert body["carbs"]["consumed_g"] == 90


async def test_dashboard_ignores_entries_from_other_days(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "dash-other-day@example.com")
    food_resp = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": "Oats",
            "serving_description": "1 bowl",
            "serving_grams": 100,
            "calories_kcal": 150,
            "protein_g": 5,
            "carbs_g": 27,
            "fat_g": 3,
        },
    )
    food_id = food_resp.json()["id"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food_id,
            "logged_at": yesterday,
            "meal_category": "breakfast",
            "quantity": 1,
            "unit": "serving",
        },
    )

    resp = await client.get("/api/v1/dashboard", headers=headers)
    assert resp.json()["calories"]["consumed"] == 0


async def test_dashboard_shows_latest_weight_as_of_requested_date(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "dash-weight@example.com")
    today = date.today()

    await client.post(
        "/api/v1/weight-entries",
        headers=headers,
        json={"logged_at": (today - timedelta(days=5)).isoformat(), "weight_kg": 85},
    )
    await client.post(
        "/api/v1/weight-entries",
        headers=headers,
        json={"logged_at": (today - timedelta(days=1)).isoformat(), "weight_kg": 83},
    )

    resp = await client.get("/api/v1/dashboard", headers=headers)
    body = resp.json()
    assert body["latest_weight_kg"] == 83
    assert body["latest_weight_logged_at"] == (today - timedelta(days=1)).isoformat()


async def test_dashboard_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code in (401, 403)
