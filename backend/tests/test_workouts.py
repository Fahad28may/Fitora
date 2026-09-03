from datetime import UTC, datetime, timedelta

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


async def _get_exercise_id(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    resp = await client.get("/api/v1/exercises", headers=headers, params={"q": name})
    matches = [e for e in resp.json() if e["name"] == name]
    assert matches, f"seed exercise {name!r} not found"
    return matches[0]["id"]


async def test_create_workout_with_exercises(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "workout-create@example.com")
    bench_id = await _get_exercise_id(client, headers, "Barbell Bench Press")
    squat_id = await _get_exercise_id(client, headers, "Barbell Back Squat")

    resp = await client.post(
        "/api/v1/workouts",
        headers=headers,
        json={
            "name": "Push Day",
            "workout_type": "routine",
            "exercises": [
                {"exercise_id": bench_id, "target_sets": 4, "target_reps": 8},
                {"exercise_id": squat_id, "target_sets": 3, "target_reps": 10},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Push Day"
    assert len(body["exercises"]) == 2
    assert body["exercises"][0]["exercise_name"] == "Barbell Bench Press"
    assert body["exercises"][0]["order_index"] == 0
    assert body["exercises"][1]["order_index"] == 1


async def test_create_workout_with_unknown_exercise_fails(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "workout-unknown-exercise@example.com")
    resp = await client.post(
        "/api/v1/workouts",
        headers=headers,
        json={
            "name": "Bad Workout",
            "workout_type": "single",
            "exercises": [{"exercise_id": "00000000-0000-0000-0000-000000000000"}],
        },
    )
    assert resp.status_code == 400


async def test_create_workout_requires_at_least_one_exercise(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "workout-empty@example.com")
    resp = await client.post(
        "/api/v1/workouts",
        headers=headers,
        json={"name": "Empty", "workout_type": "single", "exercises": []},
    )
    assert resp.status_code == 422


async def test_list_and_get_workout(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "workout-list@example.com")
    exercise_id = await _get_exercise_id(client, headers, "Plank")

    create_resp = await client.post(
        "/api/v1/workouts",
        headers=headers,
        json={
            "name": "Core",
            "workout_type": "single",
            "exercises": [{"exercise_id": exercise_id}],
        },
    )
    workout_id = create_resp.json()["id"]

    list_resp = await client.get("/api/v1/workouts", headers=headers)
    assert len(list_resp.json()) == 1

    get_resp = await client.get(f"/api/v1/workouts/{workout_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Core"


async def test_cannot_view_or_delete_another_users_workout(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "workout-owner-a@example.com")
    headers_b = await _auth_headers(client, "workout-owner-b@example.com")
    exercise_id = await _get_exercise_id(client, headers_a, "Plank")

    create_resp = await client.post(
        "/api/v1/workouts",
        headers=headers_a,
        json={
            "name": "Core",
            "workout_type": "single",
            "exercises": [{"exercise_id": exercise_id}],
        },
    )
    workout_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/workouts/{workout_id}", headers=headers_b)
    assert get_resp.status_code == 404

    delete_resp = await client.delete(f"/api/v1/workouts/{workout_id}", headers=headers_b)
    assert delete_resp.status_code == 404


async def test_delete_workout(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "workout-delete@example.com")
    exercise_id = await _get_exercise_id(client, headers, "Plank")
    create_resp = await client.post(
        "/api/v1/workouts",
        headers=headers,
        json={
            "name": "Core",
            "workout_type": "single",
            "exercises": [{"exercise_id": exercise_id}],
        },
    )
    workout_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/workouts/{workout_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/workouts", headers=headers)
    assert list_resp.json() == []


async def test_log_freeform_workout_session(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "session-log@example.com")
    exercise_id = await _get_exercise_id(client, headers, "Barbell Bench Press")
    started = datetime.now(UTC)
    ended = started + timedelta(minutes=45)

    resp = await client.post(
        "/api/v1/workout-sessions",
        headers=headers,
        json={
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "notes": "Felt strong",
            "sets": [
                {"exercise_id": exercise_id, "set_number": 1, "reps": 8, "weight_kg": 60},
                {"exercise_id": exercise_id, "set_number": 2, "reps": 8, "weight_kg": 62.5},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["workout_id"] is None
    assert len(body["sets"]) == 2
    assert body["sets"][0]["exercise_name"] == "Barbell Bench Press"
    assert body["notes"] == "Felt strong"


async def test_session_rejects_ended_before_started(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "session-invalid-time@example.com")
    exercise_id = await _get_exercise_id(client, headers, "Plank")
    started = datetime.now(UTC)
    ended = started - timedelta(minutes=10)

    resp = await client.post(
        "/api/v1/workout-sessions",
        headers=headers,
        json={
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "sets": [{"exercise_id": exercise_id, "set_number": 1, "duration_seconds": 60}],
        },
    )
    assert resp.status_code == 422


async def test_session_requires_at_least_one_set(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "session-empty@example.com")
    started = datetime.now(UTC)

    resp = await client.post(
        "/api/v1/workout-sessions",
        headers=headers,
        json={"started_at": started.isoformat(), "ended_at": started.isoformat(), "sets": []},
    )
    assert resp.status_code == 422


async def test_log_session_against_a_workout_template(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "session-template@example.com")
    exercise_id = await _get_exercise_id(client, headers, "Bodyweight Squat")

    workout_resp = await client.post(
        "/api/v1/workouts",
        headers=headers,
        json={
            "name": "Legs",
            "workout_type": "routine",
            "exercises": [{"exercise_id": exercise_id, "target_sets": 3, "target_reps": 12}],
        },
    )
    workout_id = workout_resp.json()["id"]
    started = datetime.now(UTC)

    resp = await client.post(
        "/api/v1/workout-sessions",
        headers=headers,
        json={
            "workout_id": workout_id,
            "started_at": started.isoformat(),
            "ended_at": (started + timedelta(minutes=30)).isoformat(),
            "sets": [{"exercise_id": exercise_id, "set_number": 1, "reps": 12}],
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["workout_id"] == workout_id


async def test_list_and_get_workout_session(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "session-list@example.com")
    exercise_id = await _get_exercise_id(client, headers, "Plank")
    started = datetime.now(UTC)

    create_resp = await client.post(
        "/api/v1/workout-sessions",
        headers=headers,
        json={
            "started_at": started.isoformat(),
            "ended_at": (started + timedelta(minutes=5)).isoformat(),
            "sets": [{"exercise_id": exercise_id, "set_number": 1, "duration_seconds": 60}],
        },
    )
    session_id = create_resp.json()["id"]

    list_resp = await client.get("/api/v1/workout-sessions", headers=headers)
    assert len(list_resp.json()) == 1

    get_resp = await client.get(f"/api/v1/workout-sessions/{session_id}", headers=headers)
    assert get_resp.status_code == 200


async def test_cannot_view_or_delete_another_users_session(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "session-owner-a@example.com")
    headers_b = await _auth_headers(client, "session-owner-b@example.com")
    exercise_id = await _get_exercise_id(client, headers_a, "Plank")
    started = datetime.now(UTC)

    create_resp = await client.post(
        "/api/v1/workout-sessions",
        headers=headers_a,
        json={
            "started_at": started.isoformat(),
            "ended_at": (started + timedelta(minutes=5)).isoformat(),
            "sets": [{"exercise_id": exercise_id, "set_number": 1, "duration_seconds": 60}],
        },
    )
    session_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/workout-sessions/{session_id}", headers=headers_b)
    assert get_resp.status_code == 404

    delete_resp = await client.delete(
        f"/api/v1/workout-sessions/{session_id}", headers=headers_b
    )
    assert delete_resp.status_code == 404


async def test_workouts_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/workouts")
    assert resp.status_code in (401, 403)

    resp = await client.get("/api/v1/workout-sessions")
    assert resp.status_code in (401, 403)
