import pytest
from httpx import AsyncClient

from app.api.deps import get_ai_client
from app.main import app
from tests.ai_fakes import AlwaysFailingAIClient, FakeAIClient

pytestmark = pytest.mark.asyncio


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_ai_override():
    yield
    app.dependency_overrides.pop(get_ai_client, None)


async def test_coach_without_ai_configured_returns_503(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "coach-disabled@example.com")
    resp = await client.post(
        "/api/v1/ai/coach/messages", headers=headers, json={"message": "How am I doing?"}
    )
    assert resp.status_code == 503


async def test_coach_send_message_returns_assistant_reply(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "coach-send@example.com")
    fake = FakeAIClient(["You're doing great! Keep it up."])
    app.dependency_overrides[get_ai_client] = lambda: fake

    resp = await client.post(
        "/api/v1/ai/coach/messages", headers=headers, json={"message": "How am I doing?"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "assistant"
    assert body["content"] == "You're doing great! Keep it up."


async def test_coach_system_prompt_includes_structured_data_and_safety_rules(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "coach-prompt@example.com")
    fake = FakeAIClient(["ok"])
    app.dependency_overrides[get_ai_client] = lambda: fake

    await client.post(
        "/api/v1/ai/coach/messages", headers=headers, json={"message": "Why is my weight stuck?"}
    )

    assert len(fake.calls) == 1
    system_message = fake.calls[0][0]
    assert system_message["role"] == "system"
    assert "not a doctor" in system_message["content"]
    assert "dashboard_today" in system_message["content"]
    assert "cannot take any action" in system_message["content"]

    user_message = fake.calls[0][-1]
    assert user_message["content"] == "Why is my weight stuck?"


async def test_coach_history_persists_across_messages(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "coach-history@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(["first reply"])
    await client.post(
        "/api/v1/ai/coach/messages", headers=headers, json={"message": "hello"}
    )

    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(["second reply"])
    await client.post(
        "/api/v1/ai/coach/messages", headers=headers, json={"message": "follow up"}
    )

    resp = await client.get("/api/v1/ai/coach/messages", headers=headers)
    assert resp.status_code == 200
    roles_and_content = [(m["role"], m["content"]) for m in resp.json()]
    assert roles_and_content == [
        ("user", "hello"),
        ("assistant", "first reply"),
        ("user", "follow up"),
        ("assistant", "second reply"),
    ]


async def test_coach_second_message_includes_prior_history_in_context(
    client: AsyncClient,
) -> None:
    headers = await _auth_headers(client, "coach-context@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(["first reply"])
    await client.post("/api/v1/ai/coach/messages", headers=headers, json={"message": "hello"})

    fake2 = FakeAIClient(["second reply"])
    app.dependency_overrides[get_ai_client] = lambda: fake2
    await client.post(
        "/api/v1/ai/coach/messages", headers=headers, json={"message": "follow up"}
    )

    contents = [m["content"] for m in fake2.calls[0]]
    assert "hello" in contents
    assert "first reply" in contents


async def test_coach_history_isolated_per_user(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "coach-owner-a@example.com")
    headers_b = await _auth_headers(client, "coach-owner-b@example.com")

    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(["reply for A"])
    await client.post("/api/v1/ai/coach/messages", headers=headers_a, json={"message": "hi"})

    resp_b = await client.get("/api/v1/ai/coach/messages", headers=headers_b)
    assert resp_b.json() == []


async def test_coach_clear_history(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "coach-clear@example.com")
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient(["reply"])
    await client.post("/api/v1/ai/coach/messages", headers=headers, json={"message": "hi"})

    delete_resp = await client.delete("/api/v1/ai/coach/messages", headers=headers)
    assert delete_resp.status_code == 204

    resp = await client.get("/api/v1/ai/coach/messages", headers=headers)
    assert resp.json() == []


async def test_coach_returns_503_on_provider_outage(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "coach-outage@example.com")
    app.dependency_overrides[get_ai_client] = lambda: AlwaysFailingAIClient()

    resp = await client.post(
        "/api/v1/ai/coach/messages", headers=headers, json={"message": "hi"}
    )
    assert resp.status_code == 503


async def test_coach_requires_authentication(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/ai/coach/messages", json={"message": "hi"})
    assert resp.status_code in (401, 403)

    resp = await client.get("/api/v1/ai/coach/messages")
    assert resp.status_code in (401, 403)
