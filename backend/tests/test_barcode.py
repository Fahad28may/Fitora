import asyncio

import httpx
import pytest
from httpx import AsyncClient

from app.api.deps import get_food_db_client
from app.main import app
from app.services.food_db.client import (
    OpenFoodFactsClient,
)
from app.services.food_db.exceptions import (
    FoodDbProviderError,
    ProductNotFoundError,
    UnusableProductDataError,
)
from tests.food_db_fakes import FakeFoodDbClient, RaisingFoodDbClient, sample_product

pytestmark = pytest.mark.asyncio

BARCODE = "5000112637922"


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_food_db_override():
    yield
    app.dependency_overrides.pop(get_food_db_client, None)


# --- endpoint behaviour ---------------------------------------------------


async def test_barcode_lookup_returns_the_product(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "barcode-ok@example.com")
    app.dependency_overrides[get_food_db_client] = lambda: FakeFoodDbClient(
        {BARCODE: sample_product(BARCODE)}
    )

    resp = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Test Protein Bar"
    assert body["brand"] == "TestBrand"
    assert body["source"] == "external_db"
    assert body["serving_grams"] == 60.0
    # Nutrition is stored on a per-100 g basis and reported as such.
    assert body["calories_kcal"] == 350.0


async def test_second_lookup_of_same_barcode_is_served_from_cache(
    client: AsyncClient,
) -> None:
    """The provider must not be called again for a barcode already stored --
    it keeps repeat scans fast and keeps working if the provider is down."""
    headers = await _auth_headers(client, "barcode-cache@example.com")
    fake = FakeFoodDbClient({BARCODE: sample_product(BARCODE)})
    app.dependency_overrides[get_food_db_client] = lambda: fake

    first = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)
    second = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert fake.calls == [BARCODE]


async def test_cached_barcode_is_shared_across_users(client: AsyncClient) -> None:
    """An external food is public product data, not user data, so a second
    user scanning the same barcode reuses the row rather than refetching."""
    headers_a = await _auth_headers(client, "barcode-share-a@example.com")
    headers_b = await _auth_headers(client, "barcode-share-b@example.com")
    fake = FakeFoodDbClient({BARCODE: sample_product(BARCODE)})
    app.dependency_overrides[get_food_db_client] = lambda: fake

    resp_a = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers_a)
    resp_b = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers_b)

    assert resp_a.json()["id"] == resp_b.json()["id"]
    assert fake.calls == [BARCODE]


async def test_barcode_lookup_without_provider_configured_returns_503(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "barcode-disabled@example.com")

    resp = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)

    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]


async def test_barcode_lookup_requires_authentication(client: AsyncClient) -> None:
    app.dependency_overrides[get_food_db_client] = lambda: FakeFoodDbClient({})

    resp = await client.get(f"/api/v1/foods/barcode/{BARCODE}")

    assert resp.status_code == 401


async def test_unknown_barcode_returns_404(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "barcode-missing@example.com")
    app.dependency_overrides[get_food_db_client] = lambda: FakeFoodDbClient({})

    resp = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)

    assert resp.status_code == 404
    assert "custom food" in resp.json()["detail"]


async def test_implausible_product_data_returns_422_not_a_food_row(
    client: AsyncClient,
) -> None:
    """A product whose nutrition is garbage must not be persisted -- it would
    silently corrupt calorie totals."""
    headers = await _auth_headers(client, "barcode-garbage@example.com")
    app.dependency_overrides[get_food_db_client] = lambda: RaisingFoodDbClient(
        UnusableProductDataError("implausible energy-kcal_100g: 3500")
    )

    resp = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)

    assert resp.status_code == 422
    assert "custom food" in resp.json()["detail"]

    # Nothing was cached, so a later corrected lookup still reaches the provider.
    app.dependency_overrides[get_food_db_client] = lambda: FakeFoodDbClient(
        {BARCODE: sample_product(BARCODE)}
    )
    retry = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)
    assert retry.status_code == 200, retry.text


async def test_provider_outage_returns_503(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "barcode-outage@example.com")
    app.dependency_overrides[get_food_db_client] = lambda: RaisingFoodDbClient(
        FoodDbProviderError("simulated outage")
    )

    resp = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)

    assert resp.status_code == 503
    assert "log manually" in resp.json()["detail"]


@pytest.mark.parametrize(
    "bad_barcode",
    ["abc123456", "12345", "../../etc/passwd", "5000112637922123456", "5000-112637"],
)
async def test_malformed_barcode_is_rejected_before_any_outbound_request(
    client: AsyncClient, bad_barcode: str
) -> None:
    """The barcode is interpolated into an outbound URL, so anything
    non-numeric must be refused at the boundary."""
    headers = await _auth_headers(client, f"barcode-bad-{abs(hash(bad_barcode))}@example.com")
    fake = FakeFoodDbClient({})
    app.dependency_overrides[get_food_db_client] = lambda: fake

    resp = await client.get(f"/api/v1/foods/barcode/{bad_barcode}", headers=headers)

    assert resp.status_code in (404, 422)
    assert fake.calls == []


# --- integration with the rest of nutrition -------------------------------


async def test_scanned_food_can_be_logged_to_the_diary(client: AsyncClient) -> None:
    """Regression guard: external foods have no owner, so the food-diary
    ownership check has to treat them as shared reference data or a scanned
    product becomes impossible to log."""
    headers = await _auth_headers(client, "barcode-log@example.com")
    app.dependency_overrides[get_food_db_client] = lambda: FakeFoodDbClient(
        {BARCODE: sample_product(BARCODE)}
    )

    lookup = await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers)
    food_id = lookup.json()["id"]

    resp = await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food_id,
            "logged_at": "2026-01-15",
            "meal_category": "snack",
            "quantity": 1,
            "unit": "serving",
            "source": "barcode",
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "barcode"
    # 60 g serving of a 350 kcal/100 g bar.
    assert body["calories_kcal"] == pytest.approx(210.0)


async def test_scanned_foods_do_not_appear_in_another_users_text_search(
    client: AsyncClient,
) -> None:
    """Barcode lookup is exact-match on a code the user physically has. Letting
    scanned products fall into free-text search would let one user discover
    what another has been scanning."""
    headers_a = await _auth_headers(client, "barcode-search-a@example.com")
    headers_b = await _auth_headers(client, "barcode-search-b@example.com")
    app.dependency_overrides[get_food_db_client] = lambda: FakeFoodDbClient(
        {BARCODE: sample_product(BARCODE, name="Very Distinctive Snack")}
    )

    await client.get(f"/api/v1/foods/barcode/{BARCODE}", headers=headers_a)

    resp = await client.get(
        "/api/v1/foods/search", headers=headers_b, params={"q": "Very Distinctive"}
    )

    assert resp.status_code == 200
    assert resp.json() == []


# --- HTTP client ----------------------------------------------------------

def _nutriments(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "energy-kcal_100g": 350,
        "proteins_100g": 20,
        "carbohydrates_100g": 40,
        "fat_100g": 10,
        "fiber_100g": 3,
    }
    base.update(overrides)
    return base


def _client_with_handler(handler, timeout: float = 5.0) -> OpenFoodFactsClient:
    real_client_cls = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client_cls(*args, **kwargs)  # type: ignore[arg-type]

    httpx.AsyncClient = patched  # type: ignore[misc]
    return OpenFoodFactsClient(
        base_url="https://world.openfoodfacts.org",
        timeout=timeout,
        user_agent="Fitora/test",
    )


@pytest.fixture
def restore_httpx():
    real = httpx.AsyncClient
    yield
    httpx.AsyncClient = real


async def test_client_sends_only_the_barcode_and_a_user_agent(restore_httpx) -> None:
    """Data minimisation: the provider learns the barcode and nothing about
    who scanned it."""
    seen: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(
            200,
            json={
                "status": 1,
                "product": {"product_name": "Bar", "nutriments": _nutriments()},
            },
        )

    client = _client_with_handler(handler)
    product = await client.fetch_by_barcode(BARCODE)

    assert product.name == "Bar"
    request = seen["request"]
    assert BARCODE in str(request.url)
    assert request.headers["User-Agent"] == "Fitora/test"
    assert "Authorization" not in request.headers
    assert "Cookie" not in request.headers


async def test_client_maps_404_to_product_not_found(restore_httpx) -> None:
    client = _client_with_handler(lambda request: httpx.Response(404, json={}))

    with pytest.raises(ProductNotFoundError):
        await client.fetch_by_barcode(BARCODE)


async def test_client_maps_legacy_status_zero_to_product_not_found(
    restore_httpx,
) -> None:
    """Mirrors and caches still return the older v0-style miss body."""
    client = _client_with_handler(lambda request: httpx.Response(200, json={"status": 0}))

    with pytest.raises(ProductNotFoundError):
        await client.fetch_by_barcode(BARCODE)


async def test_client_maps_server_error_to_provider_error(restore_httpx) -> None:
    client = _client_with_handler(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(FoodDbProviderError):
        await client.fetch_by_barcode(BARCODE)


async def test_client_maps_invalid_json_to_provider_error(restore_httpx) -> None:
    client = _client_with_handler(lambda request: httpx.Response(200, text="<html>nope"))

    with pytest.raises(FoodDbProviderError):
        await client.fetch_by_barcode(BARCODE)


async def test_client_enforces_a_hard_wall_clock_deadline(restore_httpx) -> None:
    """Same failure mode the AI client hit in production: httpx's `timeout`
    only bounds the gap between chunks, so a slowly-trickling response can
    outlive it. The wall-clock cap is what actually bounds the request."""

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json={"status": 1, "product": {}})

    client = _client_with_handler(slow_handler, timeout=0.1)

    with pytest.raises(FoodDbProviderError):
        await client.fetch_by_barcode(BARCODE)


async def test_client_refuses_a_non_numeric_barcode_without_a_request(
    restore_httpx,
) -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = _client_with_handler(handler)

    with pytest.raises(ProductNotFoundError):
        await client.fetch_by_barcode("../../secrets")
    assert called is False
