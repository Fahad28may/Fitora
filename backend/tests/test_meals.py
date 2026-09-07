import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TODAY = "2026-03-01"


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _create_food(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    calories: float = 100,
    serving_grams: float = 100,
) -> str:
    resp = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": name,
            "serving_description": "1 serving",
            "serving_grams": serving_grams,
            "calories_kcal": calories,
            "protein_g": 10,
            "carbs_g": 20,
            "fat_g": 5,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_meal(
    client: AsyncClient, headers: dict[str, str], name: str, items: list[dict[str, object]]
):
    return await client.post(
        "/api/v1/meals", headers=headers, json={"name": name, "items": items}
    )


async def test_create_and_read_back_a_meal_with_totals(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "meal-create@example.com")
    eggs = await _create_food(client, headers, "Eggs", calories=140)
    toast = await _create_food(client, headers, "Toast", calories=80)

    resp = await _create_meal(
        client,
        headers,
        "My Breakfast",
        [
            {"food_id": eggs, "quantity": 2, "unit": "serving"},
            {"food_id": toast, "quantity": 1, "unit": "serving"},
        ],
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "My Breakfast"
    assert len(body["items"]) == 2
    # 2x140 + 1x80
    assert body["total_calories_kcal"] == 360.0
    assert [i["food_name"] for i in body["items"]] == ["Eggs", "Toast"]


async def test_meals_are_listed_for_their_owner_only(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "meal-list-a@example.com")
    headers_b = await _auth_headers(client, "meal-list-b@example.com")
    food = await _create_food(client, headers_a, "Oats")
    await _create_meal(client, headers_a, "A's meal", [{"food_id": food, "quantity": 1}])

    list_a = await client.get("/api/v1/meals", headers=headers_a)
    list_b = await client.get("/api/v1/meals", headers=headers_b)

    assert len(list_a.json()) == 1
    assert list_b.json() == []


async def test_cannot_build_a_meal_from_another_users_custom_food(
    client: AsyncClient,
) -> None:
    """Otherwise a meal becomes a way to read someone else's private food."""
    headers_a = await _auth_headers(client, "meal-steal-a@example.com")
    headers_b = await _auth_headers(client, "meal-steal-b@example.com")
    private_food = await _create_food(client, headers_a, "A's Secret Shake")

    resp = await _create_meal(
        client, headers_b, "Stolen", [{"food_id": private_food, "quantity": 1}]
    )

    assert resp.status_code == 404


async def test_another_user_cannot_read_or_delete_a_meal(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "meal-idor-a@example.com")
    headers_b = await _auth_headers(client, "meal-idor-b@example.com")
    food = await _create_food(client, headers_a, "Rice")
    meal_id = (
        await _create_meal(client, headers_a, "A's meal", [{"food_id": food, "quantity": 1}])
    ).json()["id"]

    assert (await client.get(f"/api/v1/meals/{meal_id}", headers=headers_b)).status_code == 404
    assert (
        await client.delete(f"/api/v1/meals/{meal_id}", headers=headers_b)
    ).status_code == 404
    # Still there for its owner.
    assert (await client.get(f"/api/v1/meals/{meal_id}", headers=headers_a)).status_code == 200


async def test_logging_a_meal_creates_one_diary_entry_per_item(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "meal-log@example.com")
    eggs = await _create_food(client, headers, "Eggs", calories=140)
    toast = await _create_food(client, headers, "Toast", calories=80)
    meal_id = (
        await _create_meal(
            client,
            headers,
            "Breakfast",
            [
                {"food_id": eggs, "quantity": 2, "unit": "serving"},
                {"food_id": toast, "quantity": 1, "unit": "serving"},
            ],
        )
    ).json()["id"]

    resp = await client.post(
        f"/api/v1/meals/{meal_id}/log",
        headers=headers,
        json={"logged_at": TODAY, "meal_category": "breakfast"},
    )

    assert resp.status_code == 201, resp.text
    assert len(resp.json()) == 2

    diary = await client.get("/api/v1/food-diary", headers=headers, params={"date": TODAY})
    entries = diary.json()
    assert len(entries) == 2
    assert sum(e["calories_kcal"] for e in entries) == 360.0
    assert all(e["meal_category"] == "breakfast" for e in entries)


async def test_logged_entries_are_independent_of_the_template(
    client: AsyncClient,
) -> None:
    """Deleting the template must not erase what the user actually ate."""
    headers = await _auth_headers(client, "meal-independent@example.com")
    food = await _create_food(client, headers, "Porridge")
    meal_id = (
        await _create_meal(client, headers, "Breakfast", [{"food_id": food, "quantity": 1}])
    ).json()["id"]
    await client.post(
        f"/api/v1/meals/{meal_id}/log",
        headers=headers,
        json={"logged_at": TODAY, "meal_category": "breakfast"},
    )

    assert (await client.delete(f"/api/v1/meals/{meal_id}", headers=headers)).status_code == 204

    diary = await client.get("/api/v1/food-diary", headers=headers, params={"date": TODAY})
    assert len(diary.json()) == 1


async def test_logged_entries_can_be_removed_individually(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "meal-editable@example.com")
    eggs = await _create_food(client, headers, "Eggs")
    toast = await _create_food(client, headers, "Toast")
    meal_id = (
        await _create_meal(
            client,
            headers,
            "Breakfast",
            [{"food_id": eggs, "quantity": 1}, {"food_id": toast, "quantity": 1}],
        )
    ).json()["id"]
    logged = (
        await client.post(
            f"/api/v1/meals/{meal_id}/log",
            headers=headers,
            json={"logged_at": TODAY, "meal_category": "breakfast"},
        )
    ).json()

    resp = await client.delete(f"/api/v1/food-diary/{logged[0]['id']}", headers=headers)

    assert resp.status_code == 204
    diary = await client.get("/api/v1/food-diary", headers=headers, params={"date": TODAY})
    assert len(diary.json()) == 1


async def test_cannot_log_another_users_meal(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "meal-loginidor-a@example.com")
    headers_b = await _auth_headers(client, "meal-loginidor-b@example.com")
    food = await _create_food(client, headers_a, "Bread")
    meal_id = (
        await _create_meal(client, headers_a, "A's meal", [{"food_id": food, "quantity": 1}])
    ).json()["id"]

    resp = await client.post(
        f"/api/v1/meals/{meal_id}/log",
        headers=headers_b,
        json={"logged_at": TODAY, "meal_category": "lunch"},
    )

    assert resp.status_code == 404


async def test_meal_must_have_at_least_one_item(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "meal-empty@example.com")

    resp = await _create_meal(client, headers, "Nothing", [])

    assert resp.status_code == 422


async def test_meal_referencing_a_missing_food_is_rejected(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "meal-nofood@example.com")

    resp = await _create_meal(
        client,
        headers,
        "Ghost",
        [{"food_id": "00000000-0000-4000-8000-000000000000", "quantity": 1}],
    )

    assert resp.status_code == 404


async def test_meals_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/meals")).status_code == 401
