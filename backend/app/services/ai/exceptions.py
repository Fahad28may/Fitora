class AIDisabledError(Exception):
    """Raised when no AI provider is configured (no API key set)."""


class AIProviderError(Exception):
    """Raised when the AI provider call fails (network, timeout, non-2xx)."""


class AIOutputValidationError(Exception):
    """Raised when the model's output doesn't match the schema we require,
    even after a retry."""
