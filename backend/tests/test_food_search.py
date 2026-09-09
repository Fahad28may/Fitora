import asyncio

import httpx
import pytest
from httpx import AsyncClient

from app.api.deps import get_food_db_client
from app.main import app
from app.services.food_db.client import (
    MAX_SEARCH_RESULTS,
    OpenFoodFactsClient,
    parse_openfoodfacts_search,
)
from app.services.food_db.exceptions import FoodDbProviderError
from tests.food_db_fakes import FakeFoodDbClient, RaisingFoodDbClient, sample_product

pytestmark = pytest.mark.asyncio


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


@pytest.fixture(autouse=True)
def _clear_food_db_override():
    yield
    app.dependency_overrides.pop(get_food_db_client, None)


def _use_client(fake: object) -> None:
    app.dependency_overrides[get_food_db_client] = lambda: fake


async def _create_custom_food(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    resp = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": name,
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": 200,
            "protein_g": 10,
            "carbs_g": 20,
            "fat_g": 5,
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _off_search_body(*products: dict[str, object]) -> dict[str, object]:
    return {"count": len(products), "page_size": 20, "products": list(products)}


def _off_product(
    code: str = "3017620422003",
    *,
    name: str | None = "Test Spread",
    calories: object = 539,
) -> dict[str, object]:
    product: dict[str, object] = {
        "code": code,
        "brands": "TestBrand",
        "serving_size": "15 g",
        "serving_quantity": 15,
        "nutriments": {
            "energy-kcal_100g": calories,
            "proteins_100g": 6.3,
            "carbohydrates_100g": 57.5,
            "fat_100g": 30.9,
            "fiber_100g": 3.0,
        },
    }
    if name is not None:
        product["product_name"] = name
    return product


class TestExternalSearchIsOptIn:
    async def test_local_search_never_calls_the_provider(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "local-only@example.com")
        await _create_custom_food(client, headers, "Homemade granola")
        fake = FakeFoodDbClient({}, [sample_product()])
        _use_client(fake)

        resp = await client.get(
            "/api/v1/foods/search", headers=headers, params={"q": "granola"}
        )

        assert resp.status_code == 200, resp.text
        assert [row["name"] for row in resp.json()] == ["Homemade granola"]
        # The default must not ship a user's typing to a third party.
        assert fake.searches == []

    async def test_opting_in_reaches_the_provider(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "opt-in@example.com")
        fake = FakeFoodDbClient({}, [sample_product(name="Provider Bar")])
        _use_client(fake)

        resp = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "protein bar", "include_external": "true"},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert fake.searches == ["protein bar"]
        assert body[0]["name"] == "Provider Bar"
        # Flagged as crowd-sourced so the client can caveat it before logging.
        assert body[0]["source"] == "external_db"

    async def test_opting_in_without_a_configured_provider_is_a_503(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "no-provider@example.com")
        # No dependency override: the provider is disabled in the test env.
        resp = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "protein bar", "include_external": "true"},
        )

        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]

    async def test_local_search_still_works_with_no_provider_configured(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "no-provider-local@example.com")
        await _create_custom_food(client, headers, "Oats")

        resp = await client.get("/api/v1/foods/search", headers=headers, params={"q": "oat"})

        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestSearchCombinesSources:
    async def test_local_results_come_first_and_external_fills_the_page(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "combined@example.com")
        await _create_custom_food(client, headers, "Bar of my own")
        _use_client(FakeFoodDbClient({}, [sample_product(name="Bar from provider")]))

        resp = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "bar", "include_external": "true"},
        )

        names = [row["name"] for row in resp.json()]
        assert names == ["Bar of my own", "Bar from provider"]

    async def test_a_full_local_page_needs_no_outbound_request(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "full-page@example.com")
        for index in range(3):
            await _create_custom_food(client, headers, f"Bar {index}")
        fake = FakeFoodDbClient({}, [sample_product(name="Bar from provider")])
        _use_client(fake)

        resp = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "bar", "include_external": "true", "limit": 3},
        )

        assert len(resp.json()) == 3
        assert fake.searches == []

    async def test_later_pages_do_not_repeat_external_results(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "paged@example.com")
        fake = FakeFoodDbClient({}, [sample_product(name="Bar from provider")])
        _use_client(fake)

        resp = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "bar", "include_external": "true", "offset": 20},
        )

        # The provider is not paged, so asking it again for page two would hand
        # back the same head of its list.
        assert resp.json() == []
        assert fake.searches == []

    async def test_an_imported_product_is_cached_and_not_duplicated(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "cached@example.com")
        product = sample_product(name="Cacheable Bar")
        _use_client(FakeFoodDbClient({}, [product]))

        first = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "cacheable", "include_external": "true"},
        )
        second = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "cacheable", "include_external": "true"},
        )

        assert first.status_code == 200 and second.status_code == 200
        assert len(second.json()) == 1
        # Same row both times: a repeat search must not accumulate duplicate
        # foods, or the diary would end up referencing several copies of one
        # product.
        assert first.json()[0]["id"] == second.json()[0]["id"]

    async def test_an_imported_food_is_loggable_by_id(self, client: AsyncClient) -> None:
        headers = await _auth_headers(client, "loggable@example.com")
        _use_client(FakeFoodDbClient({}, [sample_product(name="Loggable Bar")]))

        found = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "loggable", "include_external": "true"},
        )
        food_id = found.json()[0]["id"]

        logged = await client.post(
            "/api/v1/food-diary",
            headers=headers,
            json={
                "food_id": food_id,
                "logged_at": "2026-09-09",
                "meal_category": "snack",
                "quantity": 1,
                "unit": "serving",
            },
        )
        assert logged.status_code == 201, logged.text

    async def test_a_provider_outage_degrades_to_local_results(
        self, client: AsyncClient
    ) -> None:
        headers = await _auth_headers(client, "outage@example.com")
        await _create_custom_food(client, headers, "Local fallback bar")
        _use_client(RaisingFoodDbClient(FoodDbProviderError("boom")))

        resp = await client.get(
            "/api/v1/foods/search",
            headers=headers,
            params={"q": "bar", "include_external": "true"},
        )

        # §51: the local database is the product, the provider is an extra.
        assert resp.status_code == 200
        assert [row["name"] for row in resp.json()] == ["Local fallback bar"]


class TestSearchResponseParsing:
    def test_parses_usable_products(self) -> None:
        products = parse_openfoodfacts_search(_off_search_body(_off_product()), limit=10)
        assert len(products) == 1
        assert products[0].name == "Test Spread"
        assert products[0].barcode == "3017620422003"

    def test_skips_unusable_entries_without_dropping_the_rest(self) -> None:
        body = _off_search_body(
            _off_product("1111111111111", name=None),
            _off_product("2222222222222", calories=99999),
            _off_product("3017620422003"),
        )
        products = parse_openfoodfacts_search(body, limit=10)
        # One contributor's typo must not empty the whole result list.
        assert [p.barcode for p in products] == ["3017620422003"]

    def test_skips_entries_without_a_usable_barcode(self) -> None:
        body = _off_search_body(
            _off_product("not-a-barcode"),
            {"product_name": "No code at all", "nutriments": {}},
            _off_product("3017620422003"),
        )
        assert [p.barcode for p in parse_openfoodfacts_search(body, limit=10)] == [
            "3017620422003"
        ]

    def test_deduplicates_repeated_barcodes(self) -> None:
        body = _off_search_body(_off_product(), _off_product())
        assert len(parse_openfoodfacts_search(body, limit=10)) == 1

    def test_respects_the_limit(self) -> None:
        body = _off_search_body(
            _off_product("1111111111111"),
            _off_product("2222222222222"),
            _off_product("3333333333333"),
        )
        assert len(parse_openfoodfacts_search(body, limit=2)) == 2

    def test_rejects_a_response_that_is_not_a_product_list(self) -> None:
        with pytest.raises(FoodDbProviderError):
            parse_openfoodfacts_search({"products": "nope"}, limit=10)

    def test_an_empty_result_set_is_not_an_error(self) -> None:
        assert parse_openfoodfacts_search(_off_search_body(), limit=10) == []


# --- transport behaviour --------------------------------------------------


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


async def test_search_sends_only_the_term_and_a_user_agent(restore_httpx) -> None:
    """Data minimisation: the provider learns the search term and nothing
    about who typed it."""
    seen: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200, json=_off_search_body(_off_product()))

    client = _client_with_handler(handler)
    products = await client.search_by_name("chocolate spread", limit=5)

    assert [p.name for p in products] == ["Test Spread"]
    request = seen["request"]
    assert request.url.params["search_terms"] == "chocolate spread"
    assert request.headers["User-Agent"] == "Fitora/test"
    assert "Authorization" not in request.headers
    assert "Cookie" not in request.headers


async def test_search_never_asks_for_more_than_the_page_cap(restore_httpx) -> None:
    seen: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200, json=_off_search_body())

    client = _client_with_handler(handler)
    await client.search_by_name("chocolate", limit=500)

    assert int(seen["request"].url.params["page_size"]) == MAX_SEARCH_RESULTS


async def test_search_makes_no_request_for_a_too_short_term(restore_httpx) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("a one-character term must not reach the provider")

    client = _client_with_handler(handler)
    assert await client.search_by_name("a", limit=5) == []


async def test_search_maps_a_server_error_to_a_provider_error(restore_httpx) -> None:
    client = _client_with_handler(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(FoodDbProviderError):
        await client.search_by_name("chocolate", limit=5)


async def test_search_maps_invalid_json_to_a_provider_error(restore_httpx) -> None:
    client = _client_with_handler(lambda request: httpx.Response(200, text="<html>nope"))

    with pytest.raises(FoodDbProviderError):
        await client.search_by_name("chocolate", limit=5)


async def test_search_enforces_a_hard_wall_clock_deadline(restore_httpx) -> None:
    async def slow_handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200, json=_off_search_body())

    client = _client_with_handler(slow_handler, timeout=0.1)

    with pytest.raises(FoodDbProviderError):
        await client.search_by_name("chocolate", limit=5)


async def test_search_treats_a_404_as_no_matches(restore_httpx) -> None:
    # A miss is the right reading of 404 for a product lookup; for a search it
    # only means nothing matched, which is an ordinary answer.
    client = _client_with_handler(lambda request: httpx.Response(404, json={}))

    assert await client.search_by_name("chocolate", limit=5) == []
