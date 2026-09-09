from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TODAY = date.today()


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _set_profile(client: AsyncClient, headers: dict[str, str]) -> None:
    resp = await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "date_of_birth": TODAY.replace(year=TODAY.year - 30).isoformat(),
            "sex": "male",
            "height_cm": 180,
            "activity_level": "moderate",
            "unit_system": "metric",
        },
    )
    assert resp.status_code == 200, resp.text


async def _set_goal(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    goal_type: str = "maintain_weight",
    target_weight_kg: float | None = None,
    current_weight_kg: float = 80.0,
) -> dict[str, object]:
    body: dict[str, object] = {
        "goal_type": goal_type,
        "intensity": "standard",
        "current_weight_kg": current_weight_kg,
    }
    if target_weight_kg is not None:
        body["target_weight_kg"] = target_weight_kg
    resp = await client.post("/api/v1/goals", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


async def _create_food(client: AsyncClient, headers: dict[str, str]) -> str:
    """One serving = 500 kcal / 25 g protein / 50 g carbs / 20 g fat."""
    resp = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": "Test meal",
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": 500,
            "protein_g": 25,
            "carbs_g": 50,
            "fat_g": 20,
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


async def _log_food(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    food_id: str,
    day: date,
    servings: float,
) -> None:
    resp = await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food_id,
            "logged_at": day.isoformat(),
            "meal_category": "lunch",
            "quantity": servings,
            "unit": "serving",
        },
    )
    assert resp.status_code == 201, resp.text


async def _log_weight(
    client: AsyncClient, headers: dict[str, str], *, day: date, weight_kg: float
) -> None:
    resp = await client.post(
        "/api/v1/weight-entries",
        headers=headers,
        json={"logged_at": day.isoformat(), "weight_kg": round(weight_kg, 1)},
    )
    assert resp.status_code == 201, resp.text


def _day(index: int, *, span: int = 28) -> date:
    """Chronological day `index` of a `span`-day window ending today."""
    return TODAY - timedelta(days=span - 1 - index)


async def _seed_28_days(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    servings_per_day: float = 5.0,
    start_kg: float = 80.0,
    end_kg: float = 79.0,
) -> None:
    """Food every day and a weigh-in every other day, over 28 days.

    Enough to clear every data floor in the analytics, so tests can assert on
    the numbers rather than on the "not enough data" branches.
    """
    food_id = await _create_food(client, headers)
    for index in range(28):
        await _log_food(
            client, headers, food_id=food_id, day=_day(index), servings=servings_per_day
        )
        if index % 2 == 0:
            await _log_weight(
                client,
                headers,
                day=_day(index),
                weight_kg=start_kg + (end_kg - start_kg) * index / 27,
            )


async def _summary(
    client: AsyncClient, headers: dict[str, str], **params: object
) -> dict[str, object]:
    resp = await client.get("/api/v1/analytics/summary", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


class TestAnalyticsAccess:
    async def test_summary_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/analytics/summary")).status_code == 401

    async def test_window_is_bounded(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "window@example.com")
        too_short = await client.get(
            "/api/v1/analytics/summary", headers=headers, params={"days": 1}
        )
        too_long = await client.get(
            "/api/v1/analytics/summary", headers=headers, params={"days": 5000}
        )
        assert too_short.status_code == 422
        assert too_long.status_code == 422

    async def test_one_users_data_never_appears_in_anothers_analytics(
        self, client: AsyncClient
    ) -> None:
        owner = await _auth_headers(client, "owner@example.com")
        await _set_profile(client, owner)
        await _set_goal(client, owner)
        await _seed_28_days(client, owner)

        stranger = await _auth_headers(client, "stranger@example.com")
        body = await _summary(client, stranger)

        assert body["weight_trend"]["available"] is False
        assert body["adherence"]["days_food_logged"] == 0
        assert body["macro_split"]["available"] is False


class TestEmptyAccount:
    async def test_every_block_explains_itself_instead_of_inventing_numbers(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "empty@example.com")
        body = await _summary(client, headers)

        trend = body["weight_trend"]
        assert trend["available"] is False
        assert trend["weekly_change_kg"] is None
        assert "at least two days" in trend["unavailable_reason"]

        assert body["macro_split"]["available"] is False
        assert body["macro_split"]["protein_percent"] is None
        assert body["energy_balance"]["available"] is False
        assert body["energy_balance"]["net_kcal"] is None

        adherence = body["adherence"]
        assert adherence["has_active_goal"] is False
        assert adherence["current_streak_days"] == 0
        assert adherence["calories"] == {"days_on_target": 0, "days_counted": 0}

        # Always seven, so a client can render a full week without holes.
        assert [p["weekday"] for p in body["weekday_patterns"]] == list(range(7))
        assert all(p["avg_calories_kcal"] is None for p in body["weekday_patterns"])


class TestWeightTrend:
    async def test_reports_a_rate_and_direction_from_a_steady_decline(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "trend@example.com")
        await _set_profile(client, headers)
        await _set_goal(client, headers)
        await _seed_28_days(client, headers)

        trend = (await _summary(client, headers))["weight_trend"]
        assert trend["available"] is True
        assert trend["entry_days"] == 14
        assert trend["span_days"] == 26
        # 1 kg over four weeks is about a quarter-kilo a week.
        assert trend["weekly_change_kg"] == pytest.approx(-0.26, abs=0.05)
        assert trend["direction"] == "falling"
        assert trend["fit_quality"] > 0.9
        assert trend["confidence"] == "high"

    async def test_same_day_weigh_ins_are_averaged_into_one_point(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "sameday@example.com")
        await _log_weight(client, headers, day=_day(0), weight_kg=80.0)
        await _log_weight(client, headers, day=_day(0), weight_kg=81.0)
        await _log_weight(client, headers, day=_day(27), weight_kg=79.0)

        trend = (await _summary(client, headers))["weight_trend"]
        assert trend["entry_days"] == 2
        assert trend["points"][0]["weight_kg"] == pytest.approx(80.5)

    async def test_a_rate_is_withheld_when_the_span_is_too_short(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "shortspan@example.com")
        for index in (24, 25, 26, 27):
            await _log_weight(client, headers, day=_day(index), weight_kg=80.0 - index * 0.1)

        trend = (await _summary(client, headers))["weight_trend"]
        # The line is drawable and honest; four days is not a rate.
        assert trend["available"] is True
        assert len(trend["points"]) == 4
        assert trend["weekly_change_kg"] is None
        assert "spread over" in trend["projection_unavailable_reason"]

    async def test_a_flat_trend_reads_as_steady_not_as_a_direction(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "steady@example.com")
        for index in range(0, 28, 2):
            await _log_weight(client, headers, day=_day(index), weight_kg=80.0)

        trend = (await _summary(client, headers))["weight_trend"]
        assert trend["direction"] == "steady"


class TestGoalProjection:
    async def test_projects_a_date_when_the_trend_moves_toward_the_goal(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "project@example.com")
        await _set_profile(client, headers)
        await _set_goal(client, headers, goal_type="lose_weight", target_weight_kg=75.0)
        await _seed_28_days(client, headers)

        projection = (await _summary(client, headers))["weight_trend"]["goal_projection"]
        assert projection is not None
        assert projection["target_weight_kg"] == pytest.approx(75.0)
        assert projection["estimated_weeks"] > 0
        assert date.fromisoformat(projection["estimated_date"]) > TODAY
        assert "not a promise" in projection["caveat"]

    async def test_refuses_to_project_when_the_trend_moves_away(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "wrongway@example.com")
        await _set_profile(client, headers)
        await _set_goal(client, headers, goal_type="gain_weight", target_weight_kg=90.0)
        await _seed_28_days(client, headers)

        trend = (await _summary(client, headers))["weight_trend"]
        assert trend["goal_projection"] is None
        assert "moving away" in trend["projection_unavailable_reason"]

    async def test_refuses_to_project_without_a_goal_weight(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "nogoalweight@example.com")
        await _set_profile(client, headers)
        await _set_goal(client, headers)
        await _seed_28_days(client, headers)

        trend = (await _summary(client, headers))["weight_trend"]
        assert trend["goal_projection"] is None
        assert "goal weight" in trend["projection_unavailable_reason"]


class TestAdherence:
    async def test_counts_streaks_and_on_target_days_against_the_users_own_targets(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "adherence@example.com")
        await _set_profile(client, headers)
        goal = await _set_goal(client, headers)
        food_id = await _create_food(client, headers)

        # Five consecutive days ending today, each within 10% of target.
        on_target_servings = int(goal["target_calories"]) / 500
        for index in range(23, 28):
            await _log_food(
                client, headers, food_id=food_id, day=_day(index), servings=on_target_servings
            )
        # An earlier, isolated day well under target.
        await _log_food(client, headers, food_id=food_id, day=_day(10), servings=1)

        adherence = (await _summary(client, headers))["adherence"]
        assert adherence["has_active_goal"] is True
        assert adherence["days_food_logged"] == 6
        assert adherence["current_streak_days"] == 5
        assert adherence["longest_streak_days"] == 5
        assert adherence["calories"] == {"days_on_target": 5, "days_counted": 6}

    async def test_water_is_judged_only_on_days_water_was_logged(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "water-adherence@example.com")
        await _set_profile(client, headers)
        goal = await _set_goal(client, headers)
        target_ml = int(goal["target_water_ml"])

        await client.post(
            "/api/v1/water-entries",
            headers=headers,
            json={"logged_at": _day(27).isoformat(), "amount_ml": target_ml},
        )
        await client.post(
            "/api/v1/water-entries",
            headers=headers,
            json={"logged_at": _day(26).isoformat(), "amount_ml": 200},
        )

        # Two days logged, not thirty: a day with no water entry is a day we
        # know nothing about, not a day the user drank nothing.
        assert (await _summary(client, headers))["adherence"]["water"] == {
            "days_on_target": 1,
            "days_counted": 2,
        }

    async def test_a_broken_streak_today_reports_zero(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "broken-streak@example.com")
        food_id = await _create_food(client, headers)
        for index in (24, 25, 26):
            await _log_food(client, headers, food_id=food_id, day=_day(index), servings=4)

        adherence = (await _summary(client, headers))["adherence"]
        assert adherence["current_streak_days"] == 0
        assert adherence["longest_streak_days"] == 3


class TestMacroSplitAndPatterns:
    async def test_macro_split_reports_percentages_of_logged_calories(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "macros@example.com")
        await _set_profile(client, headers)
        await _set_goal(client, headers)
        await _seed_28_days(client, headers)

        split = (await _summary(client, headers))["macro_split"]
        assert split["available"] is True
        assert split["days_counted"] == 28
        total = split["protein_percent"] + split["carbs_percent"] + split["fat_percent"]
        assert total == pytest.approx(100.0, abs=0.2)
        # 25 g protein (100 kcal) of 480 macro kcal per serving.
        assert split["protein_percent"] == pytest.approx(20.8, abs=0.2)
        assert split["target_protein_percent"] == pytest.approx(30.0, abs=1.0)

    async def test_macro_split_stays_silent_below_three_logged_days(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "thin-macros@example.com")
        food_id = await _create_food(client, headers)
        await _log_food(client, headers, food_id=food_id, day=_day(27), servings=4)

        split = (await _summary(client, headers))["macro_split"]
        assert split["available"] is False
        assert split["days_counted"] == 1
        assert "at least 3 days" in split["unavailable_reason"]

    async def test_weekday_patterns_only_sample_days_that_were_logged(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "weekdays@example.com")
        food_id = await _create_food(client, headers)
        logged_day = _day(27)
        await _log_food(client, headers, food_id=food_id, day=logged_day, servings=4)

        patterns = (await _summary(client, headers))["weekday_patterns"]
        sampled = [p for p in patterns if p["days_sampled"] > 0]
        assert len(sampled) == 1
        assert sampled[0]["weekday"] == logged_day.weekday()
        assert sampled[0]["avg_calories_kcal"] == pytest.approx(2000.0)


class TestEnergyBalance:
    async def test_compares_intake_with_an_estimate_and_says_so(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "energy@example.com")
        await _set_profile(client, headers)
        await _set_goal(client, headers)
        await _seed_28_days(client, headers)

        balance = (await _summary(client, headers))["energy_balance"]
        assert balance["available"] is True
        assert balance["avg_intake_kcal"] == pytest.approx(2500.0)
        # Mifflin-St Jeor x the "moderate" multiplier, the same path goal
        # targets use.
        assert balance["estimated_expenditure_kcal"] == pytest.approx(2750, abs=40)
        assert balance["net_kcal"] == pytest.approx(
            2500 - balance["estimated_expenditure_kcal"]
        )
        assert "not a measurement" in balance["note"]

    async def test_reported_burn_is_shown_but_not_added_to_expenditure(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "burn@example.com")
        await _set_profile(client, headers)
        await _set_goal(client, headers)
        await _seed_28_days(client, headers)
        resp = await client.post(
            "/api/v1/activity-entries",
            headers=headers,
            json={
                "logged_at": _day(27).isoformat(),
                "activity_type": "running",
                "duration_min": 40,
                "calories_burned": 400,
            },
        )
        assert resp.status_code == 201, resp.text

        balance = (await _summary(client, headers))["energy_balance"]
        assert balance["reported_activity_burn_kcal"] == 400
        # Double-counting exercise is the classic way an app talks a user into
        # eating back calories their activity level already accounted for.
        assert balance["estimated_expenditure_kcal"] < 3000
        assert "would count it twice" in balance["note"]

    async def test_needs_a_profile_to_estimate_expenditure(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "no-profile@example.com")
        food_id = await _create_food(client, headers)
        for index in (25, 26, 27):
            await _log_food(client, headers, food_id=food_id, day=_day(index), servings=5)

        balance = (await _summary(client, headers))["energy_balance"]
        assert balance["available"] is False
        assert balance["avg_intake_kcal"] == pytest.approx(2500.0)
        assert "Complete your profile" in balance["unavailable_reason"]

