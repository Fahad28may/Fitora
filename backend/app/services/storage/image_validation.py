"""Lightweight, dependency-free image validation.

We never trust the client-supplied Content-Type. Instead we sniff the leading
bytes for a known image signature. This is a magic-byte check, not a full
decode — it stops non-images and mislabeled files cheaply; a future hardening
pass could add full-decode validation (e.g. Pillow) if warranted.
"""

# Reasonable ceiling for a phone photo; bounds memory + storage per upload.
MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MiB


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """Return (content_type, extension) for a recognized image, else None."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    # WebP: "RIFF" <4-byte size> "WEBP"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None
