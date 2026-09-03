from datetime import date

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


async def _create_egg(client: AsyncClient, headers: dict[str, str]) -> dict:
    resp = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": "Egg",
            "serving_description": "1 large egg",
            "serving_grams": 50,
            "calories_kcal": 70,
            "protein_g": 6,
            "carbs_g": 0.5,
            "fat_g": 5,
            "fiber_g": 0,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_custom_food(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "food-create@example.com")
    body = await _create_egg(client, headers)
    assert body["name"] == "Egg"
    assert body["source"] == "user"
    assert body["calories_kcal"] == 70


async def test_search_finds_own_custom_food(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "food-search@example.com")
    await _create_egg(client, headers)

    resp = await client.get("/api/v1/foods/search", headers=headers, params={"q": "egg"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["name"] == "Egg"


async def test_search_is_case_insensitive(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "food-search-case@example.com")
    await _create_egg(client, headers)

    resp = await client.get("/api/v1/foods/search", headers=headers, params={"q": "EGG"})
    assert len(resp.json()) == 1


async def test_search_does_not_leak_other_users_custom_foods(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "food-owner-a@example.com")
    headers_b = await _auth_headers(client, "food-owner-b@example.com")
    await _create_egg(client, headers_a)

    resp = await client.get("/api/v1/foods/search", headers=headers_b, params={"q": "egg"})
    assert resp.json() == []


async def test_search_rejects_too_short_query(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "food-search-short@example.com")
    resp = await client.get("/api/v1/foods/search", headers=headers, params={"q": "e"})
    assert resp.status_code == 422


async def test_log_food_diary_entry_by_servings_scales_nutrition(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "diary-log@example.com")
    food = await _create_egg(client, headers)

    resp = await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food["id"],
            "logged_at": date.today().isoformat(),
            "meal_category": "breakfast",
            "quantity": 2,
            "unit": "serving",
        },
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry["calories_kcal"] == 140
    assert entry["protein_g"] == 12
    assert entry["meal_category"] == "breakfast"


async def test_log_food_diary_entry_by_grams_scales_nutrition(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "diary-log-grams@example.com")
    food = await _create_egg(client, headers)

    resp = await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food["id"],
            "logged_at": date.today().isoformat(),
            "meal_category": "snack",
            "quantity": 25,
            "unit": "gram",
        },
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry["calories_kcal"] == 35  # half of 70 kcal per 50g serving


async def test_cannot_log_another_users_custom_food(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "diary-owner-a@example.com")
    headers_b = await _auth_headers(client, "diary-owner-b@example.com")
    food = await _create_egg(client, headers_a)

    resp = await client.post(
        "/api/v1/food-diary",
        headers=headers_b,
        json={
            "food_id": food["id"],
            "logged_at": date.today().isoformat(),
            "meal_category": "breakfast",
            "quantity": 1,
            "unit": "serving",
        },
    )
    assert resp.status_code == 404


async def test_list_diary_entries_for_day(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "diary-list@example.com")
    food = await _create_egg(client, headers)
    today = date.today().isoformat()

    await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food["id"],
            "logged_at": today,
            "meal_category": "breakfast",
            "quantity": 1,
            "unit": "serving",
        },
    )

    resp = await client.get("/api/v1/food-diary", headers=headers, params={"date": today})
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["food_name"] == "Egg"


async def test_list_diary_entries_scoped_to_requested_day(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "diary-day-scope@example.com")
    food = await _create_egg(client, headers)

    await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food["id"],
            "logged_at": "2020-01-01",
            "meal_category": "breakfast",
            "quantity": 1,
            "unit": "serving",
        },
    )

    resp = await client.get(
        "/api/v1/food-diary", headers=headers, params={"date": date.today().isoformat()}
    )
    assert resp.json() == []


async def test_delete_diary_entry(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "diary-delete@example.com")
    food = await _create_egg(client, headers)
    today = date.today().isoformat()

    create_resp = await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food["id"],
            "logged_at": today,
            "meal_category": "lunch",
            "quantity": 1,
            "unit": "serving",
        },
    )
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/food-diary/{entry_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/food-diary", headers=headers, params={"date": today})
    assert list_resp.json() == []


async def test_cannot_delete_another_users_diary_entry(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "diary-delete-owner-a@example.com")
    headers_b = await _auth_headers(client, "diary-delete-owner-b@example.com")
    food = await _create_egg(client, headers_a)

    create_resp = await client.post(
        "/api/v1/food-diary",
        headers=headers_a,
        json={
            "food_id": food["id"],
            "logged_at": date.today().isoformat(),
            "meal_category": "lunch",
            "quantity": 1,
            "unit": "serving",
        },
    )
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/food-diary/{entry_id}", headers=headers_b)
    assert delete_resp.status_code == 404


async def test_nutrition_endpoints_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/foods/search", params={"q": "egg"})
    assert resp.status_code in (401, 403)
