import logging

from slowapi import Limiter

from app.core.client_ip import client_ip_key
from app.core.config import get_settings

logger = logging.getLogger("fitora")

settings = get_settings()

limiter = Limiter(
    # Not slowapi's get_remote_address: behind a proxy that returns the
    # proxy's address, putting every user in one bucket. See client_ip.py.
    key_func=client_ip_key,
    # Shared storage when Redis is configured; per-process otherwise. The
    # difference matters the moment there is more than one instance.
    storage_uri=settings.rate_limit_storage_uri,
    # If Redis is unreachable, fall back to in-memory counters instead of
    # letting the storage error escape. Without this a Redis blip 500s every
    # rate-limited route — i.e. the entire API — which is a far worse failure
    # than the one shared storage exists to fix. Degrading to per-instance
    # limits keeps *some* brute-force protection rather than none, and is
    # exactly the behaviour we had before Redis was introduced.
    in_memory_fallback_enabled=True,
    default_limits=[f"{settings.rate_limit_default_per_minute}/minute"],
)

if settings.is_production and not settings.rate_limiting_is_shared:
    logger.error(
        "Rate limiting is using in-memory storage in production. Counters are "
        "per-process, so every limit here (including login throttling) is "
        "multiplied by the number of running instances. Set REDIS_URL."
    )

if settings.is_production and settings.trusted_proxy_count == 0:
    logger.warning(
        "TRUSTED_PROXY_COUNT is 0 in production. If this app sits behind a "
        "proxy or CDN, every request will be attributed to the proxy's IP and "
        "all users will share one rate-limit bucket."
    )

login_rate_limit = f"{settings.rate_limit_login_per_minute}/minute"
ai_rate_limit = f"{settings.rate_limit_ai_per_hour}/hour"
barcode_rate_limit = f"{settings.rate_limit_barcode_per_hour}/hour"
account_rate_limit = f"{settings.rate_limit_account_per_hour}/hour"
