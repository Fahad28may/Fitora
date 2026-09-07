class FoodDbError(Exception):
    """Base class for food-database lookup failures."""


class FoodDbProviderError(FoodDbError):
    """The provider could not be reached, timed out, or returned an
    unexpected response. Distinct from "this barcode isn't in the database",
    because the client should retry a provider error but not a miss."""


class ProductNotFoundError(FoodDbError):
    """The provider was reached and does not know this barcode."""


class UnusableProductDataError(FoodDbError):
    """The provider returned a product, but its nutrition data is missing,
    malformed, or outside physically plausible bounds.

    Open Food Facts is crowd-sourced, so a product row can carry typos like
    "3500 kcal per 100 g". Feeding that into calorie targets would corrupt the
    user's goals, so an implausible product is rejected outright rather than
    surfaced with a warning -- the user can still add the food manually with
    numbers they read off the package themselves."""
