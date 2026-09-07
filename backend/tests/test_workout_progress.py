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


async def _two_exercise_ids(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    resp = await client.get("/api/v1/exercises", headers=headers, params={"limit": 2})
    rows = resp.json()
    return rows[0]["id"], rows[1]["id"]


async def _log_session(
    client: AsyncClient,
    headers: dict[str, str],
    day: date,
    sets: list[dict[str, object]],
) -> None:
    resp = await client.post(
        "/api/v1/workout-sessions",
        headers=headers,
        json={
            "started_at": f"{day.isoformat()}T09:00:00Z",
            "ended_at": f"{day.isoformat()}T10:00:00Z",
            "sets": sets,
        },
    )
    assert resp.status_code == 201, resp.text


async def test_progress_is_empty_for_a_new_user(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "prog-empty@example.com")

    resp = await client.get("/api/v1/workouts/progress", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_sessions"] == 0
    assert body["total_volume_kg"] == 0
    assert body["personal_records"] == []
    # Every week in the window is still present, so an empty chart has a shape.
    assert len(body["weekly"]) == 12


async def test_personal_record_is_the_heaviest_set_actually_lifted(
    client: AsyncClient,
) -> None:
    """Not an estimated one-rep max — a PR must be a weight the user has
    actually moved (§16, no fake precision)."""
    headers = await _auth_headers(client, "prog-pr@example.com")
    squat, bench = await _two_exercise_ids(client, headers)
    today = date.today()

    await _log_session(
        client,
        headers,
        today - timedelta(days=7),
        [{"exercise_id": squat, "set_number": 1, "reps": 5, "weight_kg": 100}],
    )
    await _log_session(
        client,
        headers,
        today,
        [
            {"exercise_id": squat, "set_number": 1, "reps": 3, "weight_kg": 120},
            {"exercise_id": bench, "set_number": 2, "reps": 8, "weight_kg": 60},
        ],
    )

    body = (await client.get("/api/v1/workouts/progress", headers=headers)).json()

    records = {r["exercise_id"]: r for r in body["personal_records"]}
    assert records[squat]["best_weight_kg"] == 120.0
    assert records[squat]["reps_at_best"] == 3
    assert records[squat]["achieved_at"] == today.isoformat()
    assert records[squat]["total_sets"] == 2
    assert records[bench]["best_weight_kg"] == 60.0
    # Heaviest first.
    assert body["personal_records"][0]["exercise_id"] == squat


async def test_more_reps_at_the_same_weight_counts_as_a_better_record(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "prog-reps@example.com")
    squat, _ = await _two_exercise_ids(client, headers)
    today = date.today()

    await _log_session(
        client,
        headers,
        today - timedelta(days=3),
        [{"exercise_id": squat, "set_number": 1, "reps": 5, "weight_kg": 100}],
    )
    await _log_session(
        client,
        headers,
        today,
        [{"exercise_id": squat, "set_number": 1, "reps": 8, "weight_kg": 100}],
    )

    body = (await client.get("/api/v1/workouts/progress", headers=headers)).json()

    assert body["personal_records"][0]["reps_at_best"] == 8


async def test_weekly_volume_and_frequency_are_bucketed_by_week(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "prog-volume@example.com")
    squat, _ = await _two_exercise_ids(client, headers)
    today = date.today()

    await _log_session(
        client,
        headers,
        today,
        [{"exercise_id": squat, "set_number": 1, "reps": 10, "weight_kg": 50}],
    )
    await _log_session(
        client,
        headers,
        today,
        [{"exercise_id": squat, "set_number": 1, "reps": 10, "weight_kg": 60}],
    )

    body = (await client.get("/api/v1/workouts/progress", headers=headers)).json()

    assert body["total_sessions"] == 2
    assert body["total_volume_kg"] == 1100.0  # 10*50 + 10*60
    this_week = body["weekly"][-1]
    assert this_week["session_count"] == 2
    assert this_week["set_count"] == 2
    assert this_week["total_volume_kg"] == 1100.0


async def test_untrained_weeks_are_reported_as_gaps_not_omitted(
    client: AsyncClient,
) -> None:
    """A consistency chart's most useful signal is the weeks you didn't
    train, so empty weeks have to be present rather than compressed away."""
    headers = await _auth_headers(client, "prog-gaps@example.com")
    squat, _ = await _two_exercise_ids(client, headers)

    await _log_session(
        client,
        headers,
        date.today(),
        [{"exercise_id": squat, "set_number": 1, "reps": 5, "weight_kg": 80}],
    )

    body = (await client.get("/api/v1/workouts/progress", headers=headers)).json()

    assert len(body["weekly"]) == 12
    assert body["active_weeks"] == 1
    assert sum(1 for w in body["weekly"] if w["session_count"] == 0) == 11


async def test_bodyweight_sets_count_toward_frequency_but_not_volume(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "prog-bodyweight@example.com")
    squat, _ = await _two_exercise_ids(client, headers)

    await _log_session(
        client,
        headers,
        date.today(),
        [{"exercise_id": squat, "set_number": 1, "reps": 20}],
    )

    body = (await client.get("/api/v1/workouts/progress", headers=headers)).json()

    assert body["total_sessions"] == 1
    assert body["total_volume_kg"] == 0
    # A set with no weight can't be a weight PR, but it is still training done.
    assert body["personal_records"] == []
    assert body["weekly"][-1]["set_count"] == 1


async def test_progress_only_covers_the_requested_window(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "prog-window@example.com")
    squat, _ = await _two_exercise_ids(client, headers)

    await _log_session(
        client,
        headers,
        date.today() - timedelta(weeks=20),
        [{"exercise_id": squat, "set_number": 1, "reps": 5, "weight_kg": 200}],
    )

    default_window = (await client.get("/api/v1/workouts/progress", headers=headers)).json()
    wide_window = (
        await client.get("/api/v1/workouts/progress", headers=headers, params={"weeks": 26})
    ).json()

    assert default_window["total_sessions"] == 0
    assert wide_window["total_sessions"] == 1
    assert wide_window["personal_records"][0]["best_weight_kg"] == 200.0


async def test_progress_is_scoped_to_the_caller(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "prog-scope-a@example.com")
    headers_b = await _auth_headers(client, "prog-scope-b@example.com")
    squat, _ = await _two_exercise_ids(client, headers_a)

    await _log_session(
        client,
        headers_a,
        date.today(),
        [{"exercise_id": squat, "set_number": 1, "reps": 5, "weight_kg": 90}],
    )

    body_b = (await client.get("/api/v1/workouts/progress", headers=headers_b)).json()

    assert body_b["total_sessions"] == 0
    assert body_b["personal_records"] == []


async def test_progress_route_is_not_swallowed_by_the_workout_id_route(
    client: AsyncClient,
) -> None:
    """Regression guard: "/progress" has to be declared before
    "/{workout_id}" or FastAPI parses it as a workout id and 422s."""
    headers = await _auth_headers(client, "prog-routing@example.com")

    resp = await client.get("/api/v1/workouts/progress", headers=headers)

    assert resp.status_code == 200
    assert "personal_records" in resp.json()


# --- per-exercise strength progression ------------------------------------


async def test_exercise_progression_reports_best_weight_per_week(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "prog-exercise@example.com")
    squat, bench = await _two_exercise_ids(client, headers)
    today = date.today()

    await _log_session(
        client,
        headers,
        today - timedelta(weeks=2),
        [
            {"exercise_id": squat, "set_number": 1, "reps": 5, "weight_kg": 100},
            {"exercise_id": squat, "set_number": 2, "reps": 5, "weight_kg": 90},
        ],
    )
    await _log_session(
        client,
        headers,
        today,
        [
            {"exercise_id": squat, "set_number": 1, "reps": 5, "weight_kg": 110},
            {"exercise_id": bench, "set_number": 2, "reps": 5, "weight_kg": 200},
        ],
    )

    resp = await client.get(
        f"/api/v1/workouts/progress/exercises/{squat}", headers=headers
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Only weeks this exercise was trained; the other exercise is excluded.
    assert [p["best_weight_kg"] for p in body["points"]] == [100.0, 110.0]
    assert body["exercise_id"] == squat


async def test_exercise_progression_does_not_interpolate_untrained_weeks(
    client: AsyncClient,
) -> None:
    """Drawing a flat line through weeks you didn't train would imply a
    strength level that was never demonstrated."""
    headers = await _auth_headers(client, "prog-nointerp@example.com")
    squat, _ = await _two_exercise_ids(client, headers)

    await _log_session(
        client,
        headers,
        date.today(),
        [{"exercise_id": squat, "set_number": 1, "reps": 5, "weight_kg": 100}],
    )

    body = (
        await client.get(f"/api/v1/workouts/progress/exercises/{squat}", headers=headers)
    ).json()

    assert len(body["points"]) == 1


async def test_exercise_progression_for_an_untrained_exercise_is_empty(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "prog-untrained@example.com")
    _, bench = await _two_exercise_ids(client, headers)

    resp = await client.get(
        f"/api/v1/workouts/progress/exercises/{bench}", headers=headers
    )

    assert resp.status_code == 200
    assert resp.json()["points"] == []


async def test_progress_rejects_an_out_of_range_window(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "prog-badweeks@example.com")

    too_wide = await client.get(
        "/api/v1/workouts/progress", headers=headers, params={"weeks": 500}
    )
    zero = await client.get(
        "/api/v1/workouts/progress", headers=headers, params={"weeks": 0}
    )

    assert too_wide.status_code == 422
    assert zero.status_code == 422


async def test_progress_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/workouts/progress")).status_code == 401
