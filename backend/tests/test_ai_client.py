import json

import httpx
import pytest

from app.services.ai.client import OpenRouterClient
from app.services.ai.exceptions import AIProviderError

pytestmark = pytest.mark.asyncio


async def test_chat_returns_message_content_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "some/model:free"
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello there"}}]})

    real_client_cls = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client_cls(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", patched)

    client = OpenRouterClient(
        api_key="test-key", base_url="https://openrouter.ai/api/v1", timeout=5
    )
    result = await client.chat(
        model="some/model:free", messages=[{"role": "user", "content": "hi"}]
    )
    assert result == "hello there"


async def test_chat_raises_on_non_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    real_client_cls = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client_cls(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", patched)

    client = OpenRouterClient(
        api_key="test-key", base_url="https://openrouter.ai/api/v1", timeout=5
    )
    with pytest.raises(AIProviderError):
        await client.chat(model="some/model:free", messages=[{"role": "user", "content": "hi"}])


async def test_chat_raises_on_malformed_response_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    real_client_cls = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client_cls(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", patched)

    client = OpenRouterClient(
        api_key="test-key", base_url="https://openrouter.ai/api/v1", timeout=5
    )
    with pytest.raises(AIProviderError):
        await client.chat(model="some/model:free", messages=[{"role": "user", "content": "hi"}])
