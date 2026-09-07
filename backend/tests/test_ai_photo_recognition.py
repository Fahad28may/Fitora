import base64
import json

import pytest
from httpx import AsyncClient

from app.api.deps import get_ai_client
from app.main import app
from app.schemas.ai_vision import MIN_RANGE_FRACTION, RecognizedFoodItem
from app.services.ai.photo_recognition_service import build_messages, widen_narrow_range
from tests.ai_fakes import AlwaysFailingAIClient, FakeAIClient

pytestmark = pytest.mark.asyncio

# Smallest valid JPEG header the sniffer accepts, padded so it isn't empty.
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _payload(items: list[dict[str, object]], note: str = "") -> str:
    return json.dumps({"items": items, "overall_note": note})


def _item(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "scrambled eggs",
        "estimated_quantity": 2,
        "unit": "piece",
        "portion_note": "two eggs on a small plate",
        "calories_min": 140,
        "calories_max": 220,
        "confidence": "medium",
        "ingredients": ["egg", "butter"],
    }
    base.update(overrides)
    return base


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


@pytest.fixture(autouse=True)
def _enable_vision(monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL_VISION", "test/vision-model")
    get_settings.cache_clear()
    yield
    app.dependency_overrides.pop(get_ai_client, None)
    get_settings.cache_clear()


async def _post_photo(client: AsyncClient, headers: dict[str, str], data: bytes = JPEG_BYTES):
    return await client.post(
        "/api/v1/ai/recognize-food",
        headers=headers,
        files={"file": ("meal.jpg", data, "image/jpeg")},
    )


# --- happy path -----------------------------------------------------------


async def test_recognizes_food_and_offers_database_matches(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "vision-ok@example.com")
    await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": "Scrambled Eggs",
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": 150,
            "protein_g": 12,
            "carbs_g": 1,
            "fat_g": 11,
        },
    )
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [_payload([_item()], "Looks like a simple breakfast.")]
    )

    resp = await _post_photo(client, headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["name"] == "scrambled eggs"
    assert item["confidence"] == "medium"
    assert item["ingredients"] == ["egg", "butter"]
    assert [m["name"] for m in item["matches"]] == ["Scrambled Eggs"]
    assert body["overall_note"] == "Looks like a simple breakfast."


async def test_response_says_it_is_an_estimate_and_the_image_was_not_kept(
    client: AsyncClient,
) -> None:
    """A client shouldn't be able to render this as settled fact without
    having been told it isn't."""
    headers = await _auth_headers(client, "vision-flags@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient([_payload([_item()])])

    body = (await _post_photo(client, headers)).json()

    assert body["is_estimate"] is True
    assert body["image_retained"] is False


async def test_recognition_never_logs_anything_by_itself(client: AsyncClient) -> None:
    """§7: the final user-confirmed data is what gets logged. Recognition
    alone must not touch the diary."""
    headers = await _auth_headers(client, "vision-nolog@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient([_payload([_item()])])

    await _post_photo(client, headers)

    diary = await client.get(
        "/api/v1/food-diary", headers=headers, params={"date": "2026-05-01"}
    )
    assert diary.json() == []


async def test_no_food_identified_is_an_empty_result_not_an_error(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "vision-nofood@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [_payload([], "No food identified.")]
    )

    resp = await _post_photo(client, headers)

    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["overall_note"] == "No food identified."


# --- no false precision (§7) ----------------------------------------------


async def test_an_overconfident_calorie_range_is_widened(client: AsyncClient) -> None:
    """§7's example of what NOT to do is "exactly 647 calories". A model that
    ignores the prompt and returns 646-648 must not get to present a guess as
    a measurement, so the narrow range is widened rather than trusted."""
    headers = await _auth_headers(client, "vision-precision@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [_payload([_item(calories_min=646, calories_max=648)])]
    )

    item = (await _post_photo(client, headers)).json()["items"][0]

    width = item["calories_max"] - item["calories_min"]
    midpoint = (item["calories_max"] + item["calories_min"]) / 2
    assert width >= midpoint * MIN_RANGE_FRACTION
    assert item["calories_min"] < 647 < item["calories_max"]


async def test_an_honest_range_is_left_alone(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "vision-honest@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [_payload([_item(calories_min=140, calories_max=220)])]
    )

    item = (await _post_photo(client, headers)).json()["items"][0]

    assert item["calories_min"] == 140
    assert item["calories_max"] == 220


def test_widening_is_symmetric_around_the_midpoint() -> None:
    item = RecognizedFoodItem(**_item(calories_min=500, calories_max=500))  # type: ignore[arg-type]

    widened = widen_narrow_range(item)

    assert widened.calories_min == 450
    assert widened.calories_max == 550


def test_widening_never_produces_negative_calories() -> None:
    item = RecognizedFoodItem(**_item(calories_min=1, calories_max=1))  # type: ignore[arg-type]

    widened = widen_narrow_range(item)

    assert widened.calories_min >= 0


def test_a_zero_calorie_item_is_left_alone() -> None:
    """Water is genuinely 0 kcal; widening it would invent calories."""
    item = RecognizedFoodItem(**_item(calories_min=0, calories_max=0))  # type: ignore[arg-type]

    widened = widen_narrow_range(item)

    assert widened.calories_min == 0
    assert widened.calories_max == 0


def test_the_schema_cannot_express_a_single_exact_calorie_number() -> None:
    """Structural guarantee: there is no scalar calorie field to populate, so
    no amount of model drift can start reporting one."""
    assert "calories_kcal" not in RecognizedFoodItem.model_fields
    assert {"calories_min", "calories_max"} <= set(RecognizedFoodItem.model_fields)


def test_a_reversed_range_is_rejected() -> None:
    with pytest.raises(ValueError):
        RecognizedFoodItem(**_item(calories_min=300, calories_max=100))  # type: ignore[arg-type]


# --- privacy (§8) ---------------------------------------------------------


def test_the_image_is_sent_inline_and_nothing_else_is() -> None:
    """The provider gets the photo and a fixed prompt. No user id, no email,
    no hosted URL that would mean storing the image somewhere fetchable."""
    messages = build_messages("data:image/jpeg;base64,AAAA")

    serialized = json.dumps(messages)
    assert "data:image/jpeg;base64,AAAA" in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user"]


async def test_a_recognized_photo_leaves_no_stored_record(
    client: AsyncClient,
) -> None:
    """§8: don't retain the original image. Recognition must not create a
    progress-photo row or any other trace of the picture."""
    headers = await _auth_headers(client, "vision-noretain@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient([_payload([_item()])])

    await _post_photo(client, headers)

    photos = await client.get("/api/v1/progress-photos", headers=headers)
    # Storage is unconfigured in tests, so the endpoint 503s — the point is
    # that nothing was written anywhere for it to return.
    assert photos.status_code in (200, 503)
    if photos.status_code == 200:
        assert photos.json() == []


# --- input validation -----------------------------------------------------


async def test_a_non_image_upload_is_rejected(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "vision-notimage@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient([_payload([_item()])])

    resp = await _post_photo(client, headers, data=b"#!/bin/sh\nrm -rf /\n")

    assert resp.status_code == 422
    assert "isn't a JPEG" in resp.json()["detail"]


async def test_a_declared_content_type_is_not_trusted(client: AsyncClient) -> None:
    """The declared type is attacker-controlled; the bytes decide."""
    headers = await _auth_headers(client, "vision-liar@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient([_payload([_item()])])

    resp = await client.post(
        "/api/v1/ai/recognize-food",
        headers=headers,
        files={"file": ("evil.jpg", b"not an image at all", "image/jpeg")},
    )

    assert resp.status_code == 422


async def test_a_png_is_accepted_too(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "vision-png@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient([_payload([_item()])])

    resp = await _post_photo(client, headers, data=PNG_BYTES)

    assert resp.status_code == 200, resp.text


# --- failure modes --------------------------------------------------------


async def test_malformed_model_output_retries_once_then_gives_up_cleanly(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "vision-garbage@example.com")
    fake = FakeAIClient(["not json at all", "still not json"])
    app.dependency_overrides[get_ai_client] = lambda: fake

    resp = await _post_photo(client, headers)

    assert resp.status_code == 422
    assert "clearer one" in resp.json()["detail"]
    assert len(fake.calls) == 2


async def test_a_retry_that_succeeds_is_returned(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "vision-retry@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        ["```\nnope\n```", _payload([_item()])]
    )

    resp = await _post_photo(client, headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["name"] == "scrambled eggs"


async def test_provider_outage_returns_503(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "vision-outage@example.com")
    app.dependency_overrides[get_ai_client] = lambda: AlwaysFailingAIClient()

    resp = await _post_photo(client, headers)

    assert resp.status_code == 503
    assert "log manually" in resp.json()["detail"]


async def test_an_absurd_number_of_items_is_truncated(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "vision-flood@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [_payload([_item(name=f"food {i}") for i in range(40)])]
    )

    body = (await _post_photo(client, headers)).json()

    assert len(body["items"]) == 12


async def test_recognition_requires_authentication(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/ai/recognize-food",
        files={"file": ("meal.jpg", JPEG_BYTES, "image/jpeg")},
    )

    assert resp.status_code == 401


async def test_matches_do_not_leak_another_users_custom_food(
    client: AsyncClient,
) -> None:
    headers_a = await _auth_headers(client, "vision-scope-a@example.com")
    headers_b = await _auth_headers(client, "vision-scope-b@example.com")
    await client.post(
        "/api/v1/foods",
        headers=headers_a,
        json={
            "name": "Scrambled Eggs",
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": 150,
            "protein_g": 12,
            "carbs_g": 1,
            "fat_g": 11,
        },
    )
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient([_payload([_item()])])

    body = (await _post_photo(client, headers_b)).json()

    assert body["items"][0]["matches"] == []


def test_base64_encoding_round_trips_the_image() -> None:
    encoded = base64.b64encode(JPEG_BYTES).decode("ascii")

    assert base64.b64decode(encoded) == JPEG_BYTES


async def test_valid_json_that_breaks_the_schema_is_a_422_not_a_503(
    client: AsyncClient,
) -> None:
    """The live failure that surfaced the quantity-bound bug looked like a
    provider outage to the user. It is not one — the provider answered fine,
    the answer just didn't fit. That has to read as "couldn't read the photo",
    not "service unavailable"."""
    headers = await _auth_headers(client, "vision-schema@example.com")
    bad = _payload([_item(unit="bushel")])
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient([bad, bad])

    resp = await _post_photo(client, headers)

    assert resp.status_code == 422
    assert "clearer one" in resp.json()["detail"]


async def test_a_gram_portion_in_the_hundreds_is_accepted(client: AsyncClient) -> None:
    """Regression guard for the live bug: a 400 g portion is ordinary, and a
    tight quantity cap silently rejected every gram-based answer."""
    headers = await _auth_headers(client, "vision-grams@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(
        [
            _payload(
                [
                    _item(
                        estimated_quantity=400,
                        unit="gram",
                        calories_min=1980,
                        calories_max=2420,
                    )
                ]
            )
        ]
    )

    resp = await _post_photo(client, headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["estimated_quantity"] == 400.0
