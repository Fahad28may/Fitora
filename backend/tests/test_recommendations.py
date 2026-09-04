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


async def _set_maintain_goal(client: AsyncClient, headers: dict[str, str]) -> int:
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
    assert goal_resp.status_code == 201, goal_resp.text
    return int(goal_resp.json()["target_calories"])


async def _create_food(
    client: AsyncClient, headers: dict[str, str], *, name: str, calories: int
) -> str:
    resp = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": name,
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": calories,
            "protein_g": 5,
            "carbs_g": 20,
            "fat_g": 2,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _log_food_on_recent_days(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    food_id: str,
    quantity: float,
    days: int,
) -> None:
    today = date.today()
    for offset in range(days):
        resp = await client.post(
            "/api/v1/food-diary",
            headers=headers,
            json={
                "food_id": food_id,
                "logged_at": (today - timedelta(days=offset)).isoformat(),
                "meal_category": "lunch",
                "quantity": quantity,
                "unit": "serving",
            },
        )
        assert resp.status_code == 201, resp.text


async def test_recommendations_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/recommendations")
    assert resp.status_code in (401, 403)


async def test_recommendations_with_no_data_prompts_setup(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "rec-empty@example.com")
    resp = await client.get("/api/v1/recommendations", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_active_goal"] is False
    assert body["days_with_food_logged"] == 0
    assert body["generated_for"] == date.today().isoformat()
    categories = {r["category"] for r in body["recommendations"]}
    # A brand-new user should be nudged to set a goal and to start logging.
    assert "consistency" in categories
    titles = " ".join(r["title"].lower() for r in body["recommendations"])
    assert "goal" in titles
    assert "log" in titles


async def test_recommendations_flags_persistent_undereating(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "rec-under@example.com")
    await _set_maintain_goal(client, headers)
    food_id = await _create_food(client, headers, name="Cracker", calories=100)
    # ~100 kcal/day for three days is far below any realistic maintain target.
    await _log_food_on_recent_days(client, headers, food_id=food_id, quantity=1, days=3)

    resp = await client.get("/api/v1/recommendations", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["days_with_food_logged"] == 3
    top = body["recommendations"][0]
    # Warnings sort ahead of suggestions/info.
    assert top["priority"] == "warning"
    assert top["category"] == "nutrition"


async def test_recommendations_flags_over_target_calories(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "rec-over@example.com")
    target = await _set_maintain_goal(client, headers)
    food_id = await _create_food(client, headers, name="Feast", calories=500)
    # Log well above target every day for three days.
    quantity = (target // 500) + 10
    await _log_food_on_recent_days(client, headers, food_id=food_id, quantity=quantity, days=3)

    resp = await client.get("/api/v1/recommendations", headers=headers)
    assert resp.status_code == 200, resp.text
    recs = resp.json()["recommendations"]
    nutrition = [r for r in recs if r["category"] == "nutrition"]
    assert any("calorie target" in r["title"].lower() for r in nutrition)
    assert all(r["priority"] != "warning" for r in nutrition)


async def test_recommendations_nudges_when_no_workouts_logged(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "rec-activity@example.com")
    await _set_maintain_goal(client, headers)
    resp = await client.get("/api/v1/recommendations", headers=headers)
    assert resp.status_code == 200, resp.text
    activity = [r for r in resp.json()["recommendations"] if r["category"] == "activity"]
    assert len(activity) == 1
    assert activity[0]["priority"] == "suggestion"
