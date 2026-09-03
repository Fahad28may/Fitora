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


async def test_list_exercises_returns_seeded_library(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "exercise-list@example.com")
    resp = await client.get("/api/v1/exercises", headers=headers)
    assert resp.status_code == 200
    exercises = resp.json()
    assert len(exercises) > 20
    assert any(e["name"] == "Barbell Bench Press" for e in exercises)


async def test_search_exercises_by_name(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "exercise-search@example.com")
    resp = await client.get("/api/v1/exercises", headers=headers, params={"q": "squat"})
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()]
    assert "Barbell Back Squat" in names
    assert "Bodyweight Squat" in names
    assert "Pull-Up" not in names


async def test_filter_exercises_by_muscle_group(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "exercise-muscle@example.com")
    resp = await client.get(
        "/api/v1/exercises", headers=headers, params={"muscle_group": "biceps"}
    )
    assert resp.status_code == 200
    names = {e["name"] for e in resp.json()}
    assert "Barbell Bicep Curl" in names
    assert "Barbell Back Squat" not in names


async def test_get_exercise_by_id(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "exercise-detail@example.com")
    list_resp = await client.get("/api/v1/exercises", headers=headers, params={"q": "plank"})
    exercise_id = list_resp.json()[0]["id"]

    resp = await client.get(f"/api/v1/exercises/{exercise_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Plank"


async def test_get_unknown_exercise_returns_404(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "exercise-404@example.com")
    resp = await client.get(
        "/api/v1/exercises/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert resp.status_code == 404


async def test_exercises_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/exercises")
    assert resp.status_code in (401, 403)
