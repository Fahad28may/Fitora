from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_default_per_minute}/minute"],
)

login_rate_limit = f"{settings.rate_limit_login_per_minute}/minute"
ai_rate_limit = f"{settings.rate_limit_ai_per_hour}/hour"
barcode_rate_limit = f"{settings.rate_limit_barcode_per_hour}/hour"
account_rate_limit = f"{settings.rate_limit_account_per_hour}/hour"
