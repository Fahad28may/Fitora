from app.services.ai.client import AIMessage
from app.services.ai.exceptions import AIProviderError


class FakeAIClient:
    """Deterministic stand-in for the AI client — the real provider isn't
    called in tests. Returns each entry in `responses` in order, one per
    `chat()` call; raises AIProviderError if exhausted."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[list[AIMessage]] = []

    async def chat(
        self,
        *,
        model: str,
        messages: list[AIMessage],
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> str:
        self.calls.append(messages)
        if not self._responses:
            raise AIProviderError("FakeAIClient exhausted")
        return self._responses.pop(0)


class AlwaysFailingAIClient:
    async def chat(
        self,
        *,
        model: str,
        messages: list[AIMessage],
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> str:
        raise AIProviderError("simulated provider outage")
