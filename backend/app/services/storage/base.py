from typing import Protocol


class ObjectStorage(Protocol):
    """Minimal object-storage interface the app depends on.

    Kept deliberately small and provider-agnostic (S3 semantics) so the
    concrete backend — MinIO today, any S3-compatible service tomorrow — is
    swappable via config, and so tests can substitute an in-memory fake.
    Objects live in a private bucket; reads are only ever exposed through
    short-lived presigned URLs, never a public object URL.
    """

    async def put(self, *, key: str, data: bytes, content_type: str) -> None: ...

    async def presigned_get_url(self, *, key: str) -> str: ...

    async def delete(self, *, key: str) -> None: ...


class StorageError(Exception):
    """Raised when the storage backend call fails."""
