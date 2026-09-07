from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _log_food(
    client: AsyncClient, headers: dict[str, str], day: date, calories: float
) -> None:
    food = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": f"Food {calories} {day}",
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": calories,
            "protein_g": 20,
            "carbs_g": 10,
            "fat_g": 5,
        },
    )
    assert food.status_code == 201, food.text
    resp = await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food.json()["id"],
            "logged_at": day.isoformat(),
            "meal_category": "lunch",
            "quantity": 1,
            "unit": "serving",
        },
    )
    assert resp.status_code == 201, resp.text


async def test_history_returns_one_point_per_day_including_empty_days(
    client: AsyncClient,
) -> None:
    """A chart that skips days with nothing logged makes gaps look like
    continuity — every day in the window has to be present."""
    headers = await _auth_headers(client, "hist-empty@example.com")

    resp = await client.get("/api/v1/dashboard/history", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["days"] == 30
    assert len(body["points"]) == 30
    assert all(p["calories_kcal"] == 0 for p in body["points"])
    # Newest last, so the series reads left-to-right as time.
    assert body["points"][-1]["date"] == date.today().isoformat()


async def test_history_totals_nutrition_per_day(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "hist-nutrition@example.com")
    today = date.today()
    await _log_food(client, headers, today, 300)
    await _log_food(client, headers, today, 200)
    await _log_food(client, headers, today - timedelta(days=2), 450)

    points = (await client.get("/api/v1/dashboard/history", headers=headers)).json()["points"]
    by_date = {p["date"]: p for p in points}

    assert by_date[today.isoformat()]["calories_kcal"] == 500.0
    assert by_date[today.isoformat()]["protein_g"] == 40.0
    assert by_date[(today - timedelta(days=2)).isoformat()]["calories_kcal"] == 450.0
    assert by_date[(today - timedelta(days=1)).isoformat()]["calories_kcal"] == 0.0


async def test_history_totals_water_and_activity(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "hist-water@example.com")
    today = date.today().isoformat()
    await client.post(
        "/api/v1/water-entries", headers=headers, json={"logged_at": today, "amount_ml": 500}
    )
    await client.post(
        "/api/v1/water-entries", headers=headers, json={"logged_at": today, "amount_ml": 250}
    )
    await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={
            "logged_at": today,
            "activity_type": "walking",
            "duration_min": 40,
            "steps": 5000,
        },
    )

    points = (await client.get("/api/v1/dashboard/history", headers=headers)).json()["points"]
    latest = points[-1]

    assert latest["water_ml"] == 750
    assert latest["activity_minutes"] == 40
    assert latest["steps"] == 5000


async def test_history_reports_no_step_data_as_null_not_zero(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "hist-nosteps@example.com")
    today = date.today().isoformat()
    await client.post(
        "/api/v1/activity-entries",
        headers=headers,
        json={"logged_at": today, "activity_type": "swimming", "duration_min": 30},
    )

    latest = (await client.get("/api/v1/dashboard/history", headers=headers)).json()["points"][-1]

    assert latest["activity_minutes"] == 30
    assert latest["steps"] is None


async def test_history_respects_the_window(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "hist-window@example.com")
    await _log_food(client, headers, date.today() - timedelta(days=40), 999)

    narrow = (await client.get("/api/v1/dashboard/history", headers=headers)).json()
    wide = (
        await client.get(
            "/api/v1/dashboard/history", headers=headers, params={"days": 60}
        )
    ).json()

    assert sum(p["calories_kcal"] for p in narrow["points"]) == 0
    assert sum(p["calories_kcal"] for p in wide["points"]) == 999.0
    assert len(wide["points"]) == 60


async def test_history_is_scoped_to_the_caller(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "hist-scope-a@example.com")
    headers_b = await _auth_headers(client, "hist-scope-b@example.com")
    await _log_food(client, headers_a, date.today(), 700)

    points_b = (await client.get("/api/v1/dashboard/history", headers=headers_b)).json()["points"]

    assert sum(p["calories_kcal"] for p in points_b) == 0


async def test_history_rejects_an_out_of_range_window(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "hist-badwindow@example.com")

    too_wide = await client.get(
        "/api/v1/dashboard/history", headers=headers, params={"days": 500}
    )
    too_narrow = await client.get(
        "/api/v1/dashboard/history", headers=headers, params={"days": 1}
    )

    assert too_wide.status_code == 422
    assert too_narrow.status_code == 422


async def test_history_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/dashboard/history")).status_code == 401
