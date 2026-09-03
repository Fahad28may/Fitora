import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.core.config import get_settings

_REDACT_KEYS = {"password", "authorization", "token", "refresh_token", "access_token"}


class RedactSensitiveFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in _REDACT_KEYS:
            if hasattr(record, key):
                setattr(record, key, "[redacted]")
        return True


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler.addFilter(RedactSensitiveFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)

    # Uvicorn's access logger otherwise double-logs request lines with request
    # bodies attached in some configs; keep it but let our formatter own it.
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
