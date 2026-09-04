import asyncio
from typing import Literal, Protocol, TypedDict

import httpx

from app.services.ai.exceptions import AIProviderError

# Bounds worst-case generation time/cost and guards against a model that
# degenerates into a very long or repetitive response (observed live against
# a free-tier model under an adversarial prompt — see commit history).
DEFAULT_MAX_TOKENS = 800


class AIMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class AIClient(Protocol):
    async def chat(
        self,
        *,
        model: str,
        messages: list[AIMessage],
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> str: ...


class OpenRouterClient:
    """Minimal OpenRouter chat-completions client.

    OpenRouter exposes an OpenAI-compatible `/chat/completions` endpoint
    across many providers/models, which is why the app's AI provider is
    configurable per docs/third-party-services.md rather than hardcoded.
    """

    def __init__(self, *, api_key: str, base_url: str, timeout: float) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def chat(
        self,
        *,
        model: str,
        messages: list[AIMessage],
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            # Recommended by OpenRouter for attribution / rate-limit routing,
            # not sensitive.
            "X-Title": "Fitora",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # httpx's `timeout` only bounds the gap *between* chunks, not
                # total request duration — a response that trickles in slowly
                # (e.g. a model stuck generating a long/repetitive reply)
                # never trips it. wait_for() is the hard backstop: a fixed
                # wall-clock deadline no matter how the bytes arrive.
                response = await asyncio.wait_for(
                    client.post(
                        f"{self._base_url}/chat/completions", headers=headers, json=payload
                    ),
                    timeout=self._timeout,
                )
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise AIProviderError("AI provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("AI provider request failed") from exc

        if response.status_code >= 400:
            raise AIProviderError(
                f"AI provider returned {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, ValueError) as exc:
            raise AIProviderError("AI provider returned an unexpected response shape") from exc
