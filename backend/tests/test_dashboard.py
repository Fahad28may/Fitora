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


async def test_dashboard_reports_no_step_data_as_null_not_zero(client: AsyncClient) -> None:
    """§16: no fake precision. A hard 0 would assert the user took no steps,
    which is a different claim from "nothing reported any"."""
    headers = await _auth_headers(client, "dash-nosteps@example.com")

    resp = await client.get("/api/v1/dashboard", headers=headers)

    activity = resp.json()["activity"]
    assert activity["steps"] is None
    assert activity["calories_burned"] is None
    assert activity["entry_count"] == 0
    assert activity["duration_min"] == 0


async def test_dashboard_sums_todays_activity(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "dash-activity@example.com")
    today = date.today().isoformat()
    for payload in (
        {"logged_at": today, "activity_type": "walking", "duration_min": 30, "steps": 4000},
        {"logged_at": today, "activity_type": "cycling", "duration_min": 45, "steps": 500},
    ):
        resp = await client.post("/api/v1/activity-entries", headers=headers, json=payload)
        assert resp.status_code == 201, resp.text
    # Yesterday's activity must not leak into today's total.
    await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={
            "logged_at": (date.today() - timedelta(days=1)).isoformat(),
            "activity_type": "running",
            "duration_min": 60,
            "steps": 9000,
        },
    )

    activity = (await client.get("/api/v1/dashboard", headers=headers)).json()["activity"]

    assert activity["entry_count"] == 2
    assert activity["duration_min"] == 75
    assert activity["steps"] == 4500


async def test_dashboard_shows_todays_workout_with_volume(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "dash-workout@example.com")
    exercises = await client.get("/api/v1/exercises", headers=headers, params={"limit": 1})
    exercise_id = exercises.json()[0]["id"]

    resp = await client.post(
        "/api/v1/workout-sessions",
        headers=headers,
        json={
            "started_at": f"{date.today().isoformat()}T09:00:00Z",
            "ended_at": f"{date.today().isoformat()}T10:00:00Z",
            "sets": [
                {"exercise_id": exercise_id, "set_number": 1, "reps": 10, "weight_kg": 60},
                {"exercise_id": exercise_id, "set_number": 2, "reps": 8, "weight_kg": 65},
            ],
        },
    )
    assert resp.status_code == 201, resp.text

    workouts = (await client.get("/api/v1/dashboard", headers=headers)).json()["todays_workouts"]

    assert len(workouts) == 1
    assert workouts[0]["set_count"] == 2
    # 10x60 + 8x65 = 1120
    assert workouts[0]["total_volume_kg"] == 1120.0


async def test_dashboard_workouts_are_scoped_to_the_day_and_the_user(
    client: AsyncClient,
) -> None:
    headers_a = await _auth_headers(client, "dash-wscope-a@example.com")
    headers_b = await _auth_headers(client, "dash-wscope-b@example.com")
    exercises = await client.get("/api/v1/exercises", headers=headers_a, params={"limit": 1})
    exercise_id = exercises.json()[0]["id"]

    await client.post(
        "/api/v1/workout-sessions",
        headers=headers_a,
        json={
            "started_at": f"{date.today().isoformat()}T09:00:00Z",
            "ended_at": f"{date.today().isoformat()}T10:00:00Z",
            "sets": [{"exercise_id": exercise_id, "set_number": 1, "reps": 5, "weight_kg": 50}],
        },
    )
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    await client.post(
        "/api/v1/workout-sessions",
        headers=headers_a,
        json={
            "started_at": f"{yesterday}T09:00:00Z",
            "ended_at": f"{yesterday}T10:00:00Z",
            "sets": [{"exercise_id": exercise_id, "set_number": 1, "reps": 5, "weight_kg": 50}],
        },
    )

    body_a = (await client.get("/api/v1/dashboard", headers=headers_a)).json()
    body_b = (await client.get("/api/v1/dashboard", headers=headers_b)).json()

    assert len(body_a["todays_workouts"]) == 1
    assert body_b["todays_workouts"] == []
