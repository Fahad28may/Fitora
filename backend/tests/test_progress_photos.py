from datetime import date

import pytest
from httpx import AsyncClient

from app.api.deps import get_object_storage
from app.main import app
from tests.storage_fakes import FailingObjectStorage, FakeObjectStorage

pytestmark = pytest.mark.asyncio

# Minimal valid PNG signature followed by padding — enough for the magic-byte
# sniff, which is all the validator inspects.
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_storage_override():
    yield
    app.dependency_overrides.pop(get_object_storage, None)


async def test_upload_without_storage_configured_returns_503(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "photo-disabled@example.com")
    resp = await client.post(
        "/api/v1/progress-photos",
        headers=headers,
        files={"file": ("me.png", _PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 503


async def test_progress_photos_require_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/progress-photos")
    assert resp.status_code in (401, 403)


async def test_upload_and_list_progress_photo(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "photo-upload@example.com")
    fake = FakeObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: fake

    resp = await client.post(
        "/api/v1/progress-photos",
        headers=headers,
        files={"file": ("me.png", _PNG_BYTES, "image/png")},
        data={"taken_at": "2026-09-01"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["taken_at"] == "2026-09-01"
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(_PNG_BYTES)
    assert body["url"].startswith("https://storage.test/")
    # The bytes actually reached storage.
    assert len(fake.objects) == 1

    list_resp = await client.get("/api/v1/progress-photos", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_upload_defaults_taken_at_to_today(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "photo-today@example.com")
    app.dependency_overrides[get_object_storage] = lambda: FakeObjectStorage()
    resp = await client.post(
        "/api/v1/progress-photos",
        headers=headers,
        files={"file": ("me.png", _PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["taken_at"] == date.today().isoformat()


async def test_upload_rejects_non_image(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "photo-nonimage@example.com")
    app.dependency_overrides[get_object_storage] = lambda: FakeObjectStorage()
    # Declares an image content-type but the bytes aren't one — must be rejected.
    resp = await client.post(
        "/api/v1/progress-photos",
        headers=headers,
        files={"file": ("evil.png", b"not really an image", "image/png")},
    )
    assert resp.status_code == 422


async def test_upload_rejects_too_large(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await _auth_headers(client, "photo-toobig@example.com")
    app.dependency_overrides[get_object_storage] = lambda: FakeObjectStorage()
    monkeypatch.setattr("app.services.progress_photo_service.MAX_PHOTO_BYTES", 10)
    resp = await client.post(
        "/api/v1/progress-photos",
        headers=headers,
        files={"file": ("me.png", _PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 422


async def test_delete_removes_from_storage_and_db(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "photo-delete@example.com")
    fake = FakeObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: fake

    upload = await client.post(
        "/api/v1/progress-photos",
        headers=headers,
        files={"file": ("me.png", _PNG_BYTES, "image/png")},
    )
    photo_id = upload.json()["id"]

    delete_resp = await client.delete(f"/api/v1/progress-photos/{photo_id}", headers=headers)
    assert delete_resp.status_code == 204
    assert fake.objects == {}

    list_resp = await client.get("/api/v1/progress-photos", headers=headers)
    assert list_resp.json() == []


async def test_cannot_delete_another_users_photo(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "photo-owner-a@example.com")
    headers_b = await _auth_headers(client, "photo-owner-b@example.com")
    shared_storage = FakeObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: shared_storage

    upload = await client.post(
        "/api/v1/progress-photos",
        headers=headers_a,
        files={"file": ("me.png", _PNG_BYTES, "image/png")},
    )
    photo_id = upload.json()["id"]

    resp = await client.delete(f"/api/v1/progress-photos/{photo_id}", headers=headers_b)
    assert resp.status_code == 404
    # B's failed delete must not have removed A's object.
    assert len(shared_storage.objects) == 1


async def test_upload_returns_503_on_storage_outage(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "photo-outage@example.com")
    app.dependency_overrides[get_object_storage] = lambda: FailingObjectStorage()
    resp = await client.post(
        "/api/v1/progress-photos",
        headers=headers,
        files={"file": ("me.png", _PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 503
