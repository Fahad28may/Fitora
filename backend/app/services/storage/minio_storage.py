import io
from datetime import timedelta
from urllib.parse import urlparse

from anyio import to_thread
from minio import Minio
from minio.error import MinioException

from app.services.storage.base import StorageError


class MinioStorage:
    """S3-compatible object storage via the MinIO SDK.

    The MinIO SDK is synchronous, so each call is dispatched to a worker
    thread to avoid blocking the event loop. `endpoint_url` is a full URL
    (e.g. http://localhost:9000 for local MinIO, or an https S3 endpoint);
    the scheme decides TLS.
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        presigned_expiry_seconds: int,
    ) -> None:
        parsed = urlparse(endpoint_url)
        # `netloc` gives host[:port] without the scheme, which is the form the
        # MinIO client expects; `secure` carries the http/https choice.
        self._client = Minio(
            parsed.netloc,
            access_key=access_key,
            secret_key=secret_key,
            secure=parsed.scheme == "https",
        )
        self._bucket = bucket
        self._expiry = timedelta(seconds=presigned_expiry_seconds)

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        def _put() -> None:
            self._client.put_object(
                self._bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )

        try:
            await to_thread.run_sync(_put)
        except MinioException as exc:
            raise StorageError("Failed to store object") from exc

    async def presigned_get_url(self, *, key: str) -> str:
        def _url() -> str:
            return self._client.presigned_get_object(self._bucket, key, expires=self._expiry)

        try:
            return await to_thread.run_sync(_url)
        except MinioException as exc:
            raise StorageError("Failed to generate download URL") from exc

    async def delete(self, *, key: str) -> None:
        def _delete() -> None:
            self._client.remove_object(self._bucket, key)

        try:
            await to_thread.run_sync(_delete)
        except MinioException as exc:
            raise StorageError("Failed to delete object") from exc
