from app.services.storage.base import StorageError


class FakeObjectStorage:
    """In-memory stand-in for object storage — no MinIO/network in tests.
    Presigned URLs are deterministic strings keyed by object key."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def presigned_get_url(self, *, key: str) -> str:
        return f"https://storage.test/{key}"

    async def delete(self, *, key: str) -> None:
        self.objects.pop(key, None)


class FailingObjectStorage:
    """Simulates a storage backend outage on write."""

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        raise StorageError("simulated storage outage")

    async def presigned_get_url(self, *, key: str) -> str:
        raise StorageError("simulated storage outage")

    async def delete(self, *, key: str) -> None:
        raise StorageError("simulated storage outage")
