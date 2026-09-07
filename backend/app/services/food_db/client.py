import asyncio
import math
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.services.food_db.exceptions import (
    FoodDbProviderError,
    ProductNotFoundError,
    UnusableProductDataError,
)

# EAN-8/UPC-A/EAN-13 and friends are all digits. Enforced here as well as at
# the API boundary because this value is interpolated into an outbound URL --
# anything non-numeric could escape the path segment.
BARCODE_PATTERN = re.compile(r"^\d{6,14}$")

# Nutrition is always normalised to a per-100 g basis: that is the basis Open
# Food Facts reports, and it keeps scaling well-defined for every product.
PER_GRAMS_BASIS = 100.0

# Plausibility bounds, per 100 g. Pure fat is ~900 kcal/100 g, so anything
# above that is a data-entry error, not a food.
MAX_CALORIES_PER_100G = 900.0
MAX_MACRO_G_PER_100G = 100.0
# Macros get a little slack over 100 g because independently rounded per-100 g
# values legitimately sum slightly above 100.
MAX_MACRO_SUM_G_PER_100G = 105.0

MAX_SERVING_GRAMS = 5000.0
MAX_NAME_LENGTH = 200
MAX_BRAND_LENGTH = 120
MAX_SERVING_DESCRIPTION_LENGTH = 120

# Fallback when the provider has no serving size for the product. Without one
# the food could be created but never logged by the "serving" unit, so fall
# back to the 100 g basis the nutrition is already expressed in.
DEFAULT_SERVING_DESCRIPTION = "100 g"


@dataclass(frozen=True)
class ExternalProduct:
    """A validated product from an external food database, normalised to a
    per-100 g nutrition basis."""

    barcode: str
    name: str
    brand: str | None
    serving_description: str
    serving_grams: float
    per_grams: float
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None


class FoodDbClient(Protocol):
    async def fetch_by_barcode(self, barcode: str) -> ExternalProduct: ...


def _coerce_number(value: object) -> float | None:
    """Open Food Facts returns numbers as either JSON numbers or strings, and
    occasionally as an empty string meaning "not filled in"."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _clean_text(value: object, *, max_length: int) -> str | None:
    """Provider text is untrusted free-form input from contributors: collapse
    whitespace and truncate to what the column can hold."""
    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.split())
    return collapsed[:max_length] or None


def _require_macro(nutriments: dict[str, object], key: str) -> float:
    value = _coerce_number(nutriments.get(key))
    if value is None:
        raise UnusableProductDataError(f"missing {key}")
    if value < 0 or value > MAX_MACRO_G_PER_100G:
        raise UnusableProductDataError(f"implausible {key}: {value}")
    return value


def parse_openfoodfacts_product(
    barcode: str, product: dict[str, object]
) -> ExternalProduct:
    """Turn one Open Food Facts product into a validated `ExternalProduct`, or
    raise `UnusableProductDataError`.

    A free function rather than a method so the validation rules can be tested
    directly, without a transport in the way."""
    name = _clean_text(product.get("product_name"), max_length=MAX_NAME_LENGTH)
    if name is None:
        raise UnusableProductDataError("product has no name")

    raw_nutriments = product.get("nutriments")
    if not isinstance(raw_nutriments, dict):
        raise UnusableProductDataError("product has no nutriments")
    nutriments: dict[str, object] = raw_nutriments

    calories = _coerce_number(nutriments.get("energy-kcal_100g"))
    if calories is None:
        raise UnusableProductDataError("missing energy-kcal_100g")
    if calories < 0 or calories > MAX_CALORIES_PER_100G:
        raise UnusableProductDataError(f"implausible energy-kcal_100g: {calories}")

    protein = _require_macro(nutriments, "proteins_100g")
    carbs = _require_macro(nutriments, "carbohydrates_100g")
    fat = _require_macro(nutriments, "fat_100g")
    if protein + carbs + fat > MAX_MACRO_SUM_G_PER_100G:
        raise UnusableProductDataError("macros sum to more than 100 g per 100 g")

    # Fibre is genuinely optional in the source data, so a missing value is not
    # an error -- but a present-and-absurd value is still not worth keeping.
    fiber = _coerce_number(nutriments.get("fiber_100g"))
    if fiber is not None and (fiber < 0 or fiber > MAX_MACRO_G_PER_100G):
        fiber = None

    serving_grams = _coerce_number(product.get("serving_quantity"))
    if serving_grams is None or not (0 < serving_grams <= MAX_SERVING_GRAMS):
        serving_grams = PER_GRAMS_BASIS
        serving_description = DEFAULT_SERVING_DESCRIPTION
    else:
        serving_description = (
            _clean_text(
                product.get("serving_size"), max_length=MAX_SERVING_DESCRIPTION_LENGTH
            )
            or f"{serving_grams:g} g"
        )

    return ExternalProduct(
        barcode=barcode,
        name=name,
        brand=_clean_text(product.get("brands"), max_length=MAX_BRAND_LENGTH),
        serving_description=serving_description,
        serving_grams=serving_grams,
        per_grams=PER_GRAMS_BASIS,
        calories_kcal=calories,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
        fiber_g=fiber,
    )


class OpenFoodFactsClient:
    """Open Food Facts (https://world.openfoodfacts.org) -- free, open data, no
    account or API key. Their terms ask API users to send a descriptive
    User-Agent so they can identify traffic, which `user_agent` supplies.

    Only the barcode is sent. No user identifier, no auth header, nothing about
    who is scanning."""

    # Requesting only the fields we use keeps the response small; a full Open
    # Food Facts product document is hundreds of keys.
    _FIELDS = "product_name,brands,serving_size,serving_quantity,nutriments"

    def __init__(self, *, base_url: str, timeout: float, user_agent: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._user_agent = user_agent

    async def fetch_by_barcode(self, barcode: str) -> ExternalProduct:
        if not BARCODE_PATTERN.match(barcode):
            raise ProductNotFoundError("not a valid barcode")

        url = f"{self._base_url}/api/v2/product/{barcode}.json"
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # Same hard deadline as the AI client: httpx's `timeout` only
                # bounds the gap between chunks, so a slowly-trickling response
                # can outlive it indefinitely. wait_for is the wall-clock cap.
                response = await asyncio.wait_for(
                    client.get(url, headers=headers, params={"fields": self._FIELDS}),
                    timeout=self._timeout,
                )
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise FoodDbProviderError("food database request timed out") from exc
        except httpx.HTTPError as exc:
            raise FoodDbProviderError("food database request failed") from exc

        if response.status_code == 404:
            raise ProductNotFoundError(barcode)
        if response.status_code >= 400:
            raise FoodDbProviderError(f"food database returned {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise FoodDbProviderError("food database returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise FoodDbProviderError("food database returned an unexpected shape")

        # v2 answers a miss with 404, but the older v0-style body (status: 0)
        # still shows up behind caches and mirrors.
        if body.get("status") == 0:
            raise ProductNotFoundError(barcode)

        product = body.get("product")
        if not isinstance(product, dict):
            raise ProductNotFoundError(barcode)

        return parse_openfoodfacts_product(barcode, product)


__all__ = [
    "BARCODE_PATTERN",
    "ExternalProduct",
    "FoodDbClient",
    "OpenFoodFactsClient",
    "parse_openfoodfacts_product",
]
