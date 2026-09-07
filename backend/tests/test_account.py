import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_object_storage
from app.main import app
from app.models.audit import AuditEvent, AuditEventType, ConsentRecord
from app.models.nutrition import Food, FoodDiaryEntry
from app.models.user import User, UserSession
from app.models.weight_entry import WeightEntry
from tests.storage_fakes import FakeObjectStorage

pytestmark = pytest.mark.asyncio

PASSWORD = "correct-horse-battery"
DELETE_PHRASE = "DELETE MY ACCOUNT"


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def _seed_some_data(client: AsyncClient, headers: dict[str, str]) -> str:
    """A little of everything, so export and deletion have something to act on."""
    await client.post(
        "/api/v1/weight-entries",
        headers=headers,
        json={"logged_at": "2026-01-10", "weight_kg": 80.5},
    )
    await client.post(
        "/api/v1/water-entries",
        headers=headers,
        json={"logged_at": "2026-01-10", "amount_ml": 500},
    )
    food = await client.post(
        "/api/v1/foods",
        headers=headers,
        json={
            "name": "Export Test Food",
            "serving_description": "1 serving",
            "serving_grams": 100,
            "calories_kcal": 200,
            "protein_g": 10,
            "carbs_g": 20,
            "fat_g": 5,
        },
    )
    assert food.status_code == 201, food.text
    food_id = food.json()["id"]
    await client.post(
        "/api/v1/food-diary",
        headers=headers,
        json={
            "food_id": food_id,
            "logged_at": "2026-01-10",
            "meal_category": "lunch",
            "quantity": 1,
            "unit": "serving",
        },
    )
    return food_id


@pytest.fixture(autouse=True)
def _clear_storage_override():
    yield
    app.dependency_overrides.pop(get_object_storage, None)


# --- export ---------------------------------------------------------------


async def test_export_returns_every_category_of_user_data(client: AsyncClient) -> None:
    headers = await _register(client, "export-me@example.com")
    await _seed_some_data(client, headers)

    resp = await client.get("/api/v1/account/export", headers=headers)

    assert resp.status_code == 200, resp.text
    assert "attachment" in resp.headers["content-disposition"]
    data = json.loads(resp.text)

    assert data["account"]["email"] == "export-me@example.com"
    assert len(data["weight_entries"]) == 1
    assert len(data["water_entries"]) == 1
    assert len(data["custom_foods"]) == 1
    assert len(data["food_diary"]) == 1
    assert data["food_diary"][0]["food_name"] == "Export Test Food"
    # Every documented category is present even when empty, so a reader can
    # tell "you have none of these" from "we forgot to include these".
    for key in (
        "goals",
        "body_measurements",
        "activity_entries",
        "workouts",
        "workout_sessions",
        "progress_photos",
        "ai_messages",
        "consent_records",
        "audit_events",
    ):
        assert key in data, key


async def test_export_never_includes_credentials(client: AsyncClient) -> None:
    """A data export must not become a second place the password hash lives."""
    headers = await _register(client, "export-secrets@example.com")

    resp = await client.get("/api/v1/account/export", headers=headers)

    body = resp.text
    assert "password_hash" not in body
    assert "refresh_token" not in body
    assert PASSWORD not in body


async def test_export_only_returns_the_callers_own_data(client: AsyncClient) -> None:
    headers_a = await _register(client, "export-a@example.com")
    headers_b = await _register(client, "export-b@example.com")
    await _seed_some_data(client, headers_a)

    resp = await client.get("/api/v1/account/export", headers=headers_b)

    data = json.loads(resp.text)
    assert data["account"]["email"] == "export-b@example.com"
    assert data["weight_entries"] == []
    assert data["custom_foods"] == []


async def test_export_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/account/export")
    assert resp.status_code == 401


# --- deletion -------------------------------------------------------------


async def test_delete_account_removes_the_user_and_all_owned_rows(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _register(client, "delete-me@example.com")
    await _seed_some_data(client, headers)

    resp = await client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"password": PASSWORD, "confirmation": DELETE_PHRASE},
    )

    assert resp.status_code == 204, resp.text

    users = (
        await db_session.execute(select(User).where(User.email == "delete-me@example.com"))
    ).scalars().all()
    assert users == []
    for model in (WeightEntry, FoodDiaryEntry, UserSession):
        remaining = (await db_session.execute(select(model))).scalars().all()
        assert remaining == [], model.__name__
    # The user's custom food goes with them; the seeded system exercises stay.
    foods = (await db_session.execute(select(Food))).scalars().all()
    assert foods == []


async def test_deleted_account_can_no_longer_authenticate(client: AsyncClient) -> None:
    headers = await _register(client, "delete-auth@example.com")

    await client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"password": PASSWORD, "confirmation": DELETE_PHRASE},
    )

    assert (await client.get("/api/v1/dashboard", headers=headers)).status_code == 401
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "delete-auth@example.com", "password": PASSWORD},
    )
    assert login.status_code == 401


async def test_delete_requires_the_correct_password(client: AsyncClient) -> None:
    """A stolen access token alone must not be enough to destroy an account."""
    headers = await _register(client, "delete-wrongpw@example.com")

    resp = await client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"password": "not-the-password", "confirmation": DELETE_PHRASE},
    )

    assert resp.status_code == 401
    assert (await client.get("/api/v1/dashboard", headers=headers)).status_code == 200


async def test_delete_requires_the_exact_confirmation_phrase(client: AsyncClient) -> None:
    headers = await _register(client, "delete-noconfirm@example.com")

    resp = await client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"password": PASSWORD, "confirmation": "delete my account"},
    )

    assert resp.status_code == 400
    assert (await client.get("/api/v1/dashboard", headers=headers)).status_code == 200


async def test_delete_removes_progress_photo_objects_from_storage(
    client: AsyncClient,
) -> None:
    """A deleted row whose object survives is a private image nobody can find
    to remove, so the objects have to go too."""
    storage = FakeObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    headers = await _register(client, "delete-photos@example.com")

    upload = await client.post(
        "/api/v1/progress-photos",
        headers=headers,
        files={"file": ("p.png", _PNG_BYTES, "image/png")},
    )
    assert upload.status_code == 201, upload.text
    assert len(storage.objects) == 1

    resp = await client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"password": PASSWORD, "confirmation": DELETE_PHRASE},
    )

    assert resp.status_code == 204, resp.text
    assert storage.objects == {}


async def test_delete_does_not_touch_another_users_data(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers_a = await _register(client, "delete-isolation-a@example.com")
    headers_b = await _register(client, "delete-isolation-b@example.com")
    await _seed_some_data(client, headers_a)
    await _seed_some_data(client, headers_b)

    await client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers_a,
        json={"password": PASSWORD, "confirmation": DELETE_PHRASE},
    )

    survivors = (await db_session.execute(select(User))).scalars().all()
    assert [u.email for u in survivors] == ["delete-isolation-b@example.com"]
    weights = (await db_session.execute(select(WeightEntry))).scalars().all()
    assert len(weights) == 1


async def test_delete_anonymizes_rather_than_erases_audit_and_consent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The security trail and the consent ledger have to outlive the account
    they describe, while ceasing to identify anyone."""
    headers = await _register(client, "delete-audit@example.com")
    await client.put(
        "/api/v1/account/consents",
        headers=headers,
        json={"consent_type": "analytics", "granted": True},
    )

    await client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"password": PASSWORD, "confirmation": DELETE_PHRASE},
    )

    events = (await db_session.execute(select(AuditEvent))).scalars().all()
    consents = (await db_session.execute(select(ConsentRecord))).scalars().all()
    assert events, "audit trail must survive account deletion"
    assert consents, "consent ledger must survive account deletion"
    assert all(e.user_id is None for e in events)
    assert all(c.user_id is None for c in consents)
    assert any(e.event_type == AuditEventType.ACCOUNT_DELETED for e in events)


# --- consent --------------------------------------------------------------


async def test_consents_default_to_not_granted(client: AsyncClient) -> None:
    """§30: no pre-selected optional consent."""
    headers = await _register(client, "consent-default@example.com")

    resp = await client.get("/api/v1/account/consents", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["consents"] == {
        "health_data": False,
        "ai_processing": False,
        "wearable_access": False,
        "analytics": False,
    }
    assert body["policy_version"]


async def test_consent_can_be_granted_then_withdrawn(client: AsyncClient) -> None:
    headers = await _register(client, "consent-toggle@example.com")

    granted = await client.put(
        "/api/v1/account/consents",
        headers=headers,
        json={"consent_type": "ai_processing", "granted": True},
    )
    assert granted.status_code == 200, granted.text
    state = await client.get("/api/v1/account/consents", headers=headers)
    assert state.json()["consents"]["ai_processing"] is True

    await client.put(
        "/api/v1/account/consents",
        headers=headers,
        json={"consent_type": "ai_processing", "granted": False},
    )
    state = await client.get("/api/v1/account/consents", headers=headers)
    assert state.json()["consents"]["ai_processing"] is False


async def test_consent_history_is_append_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Withdrawing consent must add a row, not edit the old one — otherwise
    there is no record of what was agreed to and when."""
    headers = await _register(client, "consent-history@example.com")

    for granted in (True, False, True):
        await client.put(
            "/api/v1/account/consents",
            headers=headers,
            json={"consent_type": "analytics", "granted": granted},
        )

    records = (
        await db_session.execute(
            select(ConsentRecord).order_by(ConsentRecord.recorded_at)
        )
    ).scalars().all()
    assert [r.granted for r in records] == [True, False, True]


async def test_consent_is_scoped_to_the_caller(client: AsyncClient) -> None:
    headers_a = await _register(client, "consent-scope-a@example.com")
    headers_b = await _register(client, "consent-scope-b@example.com")

    await client.put(
        "/api/v1/account/consents",
        headers=headers_a,
        json={"consent_type": "analytics", "granted": True},
    )

    state_b = await client.get("/api/v1/account/consents", headers=headers_b)
    assert state_b.json()["consents"]["analytics"] is False


# --- audit ----------------------------------------------------------------


async def test_login_and_registration_are_audited(client: AsyncClient) -> None:
    headers = await _register(client, "audit-login@example.com")
    await client.post(
        "/api/v1/auth/login",
        json={"email": "audit-login@example.com", "password": PASSWORD},
    )

    resp = await client.get("/api/v1/account/security-events", headers=headers)

    assert resp.status_code == 200, resp.text
    types = {e["event_type"] for e in resp.json()}
    assert "user_registered" in types
    assert "login_succeeded" in types


async def test_failed_login_is_audited_without_storing_the_address(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Repeated failures are worth spotting, but the audit log must not become
    a store of email addresses."""
    await client.post(
        "/api/v1/auth/login",
        json={"email": "never-registered@example.com", "password": "wrong-password"},
    )

    events = (
        await db_session.execute(
            select(AuditEvent).where(AuditEvent.event_type == AuditEventType.LOGIN_FAILED)
        )
    ).scalars().all()

    assert len(events) == 1
    metadata = events[0].event_metadata
    assert "never-registered@example.com" not in json.dumps(metadata)
    assert len(str(metadata["email_hash"])) == 64


async def test_security_events_are_scoped_to_the_caller(client: AsyncClient) -> None:
    headers_a = await _register(client, "audit-scope-a@example.com")
    headers_b = await _register(client, "audit-scope-b@example.com")

    events_b = await client.get("/api/v1/account/security-events", headers=headers_b)

    assert events_b.status_code == 200
    assert all(e["event_type"] != "login_succeeded" for e in events_b.json())
    # A's registration event must not show up in B's history.
    assert len(events_b.json()) == 1
    events_a = await client.get("/api/v1/account/security-events", headers=headers_a)
    assert events_a.status_code == 200


# Smallest valid PNG (magic bytes + minimal IHDR), enough for the upload
# validator, which sniffs the header rather than trusting Content-Type.
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
