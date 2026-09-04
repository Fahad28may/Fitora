from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ProgressPhotoOut(BaseModel):
    id: UUID
    taken_at: date
    content_type: str
    size_bytes: int
    # Short-lived presigned URL, regenerated on each read — never a stable
    # public URL. Clients must not cache it past its expiry.
    url: str
    created_at: datetime
