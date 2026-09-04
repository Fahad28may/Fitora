import json

import pytest
from httpx import AsyncClient

from app.api.deps import get_ai_client
from app.main import app
from tests.ai_fakes import AlwaysFailingAIClient, FakeAIClient

pytestmark = pytest.mark.asyncio


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_ai_override():
    yield
    app.dependency_overrides.pop(get_ai_client, None)


def _propose(action: str, parameters: dict[str, object], summary: str = "") -> str:
    return json.dumps({"action": action, "parameters": parameters, "summary": summary})


async def _create_food(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    resp = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": name,
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": 90,
            "protein_g": 1,
            "carbs_g": 23,
            "fat_g": 0,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# --- propose (read-only) ---


async def test_propose_without_ai_configured_returns_503(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-disabled@example.com")
    resp = await client.post(
        "/api/v1/ai/actions/propose", headers=headers, json={"message": "log my weight at 80kg"}
    )
    assert resp.status_code == 503


async def test_propose_requires_authentication(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/ai/actions/propose", json={"message": "hi"})
    assert resp.status_code in (401, 403)


async def test_propose_log_weight_is_read_only(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-weight-propose@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [_propose("log_weight", {"weight_kg": 80})]
    )

    resp = await client.post(
        "/api/v1/ai/actions/propose", headers=headers, json={"message": "log my weight at 80kg"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "log_weight"
    assert body["executable"] is True
    assert body["parameters"]["weight_kg"] == 80

    # Proposing must not write anything.
    weights = await client.get("/api/v1/weight-entries", headers=headers)
    assert weights.json() == []


async def test_propose_unmappable_request_returns_none(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-none@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [_propose("none", {}, "I can only log weight, water, or food.")]
    )
    resp = await client.post(
        "/api/v1/ai/actions/propose", headers=headers, json={"message": "book me a flight"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "none"
    assert body["executable"] is False


async def test_propose_rejects_out_of_range_parameters(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-range@example.com")
    # Model claims log_weight but with an impossible value — backend must not
    # accept a value a user could never enter manually (max 500 kg).
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [_propose("log_weight", {"weight_kg": 100000})] * 2
    )
    resp = await client.post(
        "/api/v1/ai/actions/propose", headers=headers, json={"message": "log 100000 kg"}
    )
    assert resp.status_code == 422


async def test_propose_invalid_json_twice_returns_422(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-badjson@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(["not json", "still not json"])
    resp = await client.post(
        "/api/v1/ai/actions/propose", headers=headers, json={"message": "log weight"}
    )
    assert resp.status_code == 422


async def test_propose_returns_503_on_provider_outage(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-outage@example.com")
    app.dependency_overrides[get_ai_client] = lambda: AlwaysFailingAIClient()
    resp = await client.post(
        "/api/v1/ai/actions/propose", headers=headers, json={"message": "log weight 80"}
    )
    assert resp.status_code == 503


async def test_propose_log_food_returns_matches(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-food-propose@example.com")
    await _create_food(client, headers, "Banana")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [
            _propose(
                "log_food",
                {
                    "food_query": "banana",
                    "quantity": 1,
                    "unit": "serving",
                    "meal_category": "breakfast",
                },
            )
        ]
    )
    resp = await client.post(
        "/api/v1/ai/actions/propose",
        headers=headers,
        json={"message": "I had a banana for breakfast"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "log_food"
    assert body["executable"] is True
    assert any(m["name"] == "Banana" for m in body["food_matches"])


# --- confirm (deterministic write, no AI) ---


async def test_confirm_log_weight_writes_and_needs_no_ai(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-weight-confirm@example.com")
    # No AI override on purpose: confirm must work even with AI disabled.
    resp = await client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action": "log_weight", "weight_kg": 82.5},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["action"] == "log_weight"
    assert body["status"] == "executed"

    weights = await client.get("/api/v1/weight-entries", headers=headers)
    assert len(weights.json()) == 1
    assert weights.json()[0]["weight_kg"] == 82.5


async def test_confirm_log_water_writes(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-water-confirm@example.com")
    resp = await client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action": "log_water", "amount_ml": 500},
    )
    assert resp.status_code == 201, resp.text

    dashboard = await client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.json()["water"]["consumed_ml"] == 500


async def test_confirm_log_food_writes(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-food-confirm@example.com")
    food_id = await _create_food(client, headers, "Oats")
    resp = await client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={
            "action": "log_food",
            "food_id": food_id,
            "quantity": 1,
            "unit": "serving",
            "meal_category": "breakfast",
        },
    )
    assert resp.status_code == 201, resp.text

    dashboard = await client.get("/api/v1/dashboard", headers=headers)
    assert dashboard.json()["calories"]["consumed"] == 90


async def test_confirm_rejects_out_of_range_weight(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "act-confirm-range@example.com")
    resp = await client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers,
        json={"action": "log_weight", "weight_kg": 100000},
    )
    assert resp.status_code == 422


async def test_confirm_cannot_log_another_users_private_food(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "act-food-owner-a@example.com")
    headers_b = await _auth_headers(client, "act-food-owner-b@example.com")
    food_id = await _create_food(client, headers_a, "SecretSnack")

    resp = await client.post(
        "/api/v1/ai/actions/confirm",
        headers=headers_b,
        json={
            "action": "log_food",
            "food_id": food_id,
            "quantity": 1,
            "unit": "serving",
            "meal_category": "snack",
        },
    )
    assert resp.status_code == 404


async def test_confirm_requires_authentication(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/ai/actions/confirm", json={"action": "log_weight", "weight_kg": 80}
    )
    assert resp.status_code in (401, 403)
