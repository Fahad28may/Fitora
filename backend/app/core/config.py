from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_secret_key: str = Field(default="", alias="APP_SECRET_KEY")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./fitora_dev.db", alias="DATABASE_URL"
    )
    database_url_sync: str = Field(
        default="sqlite:///./fitora_dev.db", alias="DATABASE_URL_SYNC"
    )

    # Empty by default, like every other optional backing service here.
    # A non-empty default would make every dev machine and CI run try to
    # reach a Redis that isn't there.
    redis_url: str = Field(default="", alias="REDIS_URL")

    # How many reverse proxies sit in front of the app. 0 = exposed directly
    # (also correct for local dev). Vercel/Cloudflare/a single nginx = 1.
    # Used ONLY to work out the real client IP for rate limiting — see
    # app/core/client_ip.py for why the exact number matters.
    trusted_proxy_count: int = Field(default=0, alias="TRUSTED_PROXY_COUNT", ge=0, le=10)

    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=15, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=30, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS"
    )

    rate_limit_login_per_minute: int = Field(
        default=5, alias="RATE_LIMIT_LOGIN_PER_MINUTE"
    )
    rate_limit_default_per_minute: int = Field(
        default=60, alias="RATE_LIMIT_DEFAULT_PER_MINUTE"
    )

    cors_allowed_origins: str = Field(
        default="http://localhost:19006,http://localhost:8081",
        alias="CORS_ALLOWED_ORIGINS",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    ai_provider: str = Field(default="openrouter", alias="AI_PROVIDER")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_api_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="AI_API_BASE_URL"
    )
    ai_model_parsing: str = Field(
        default="nvidia/nemotron-3.5-lightning:free", alias="AI_MODEL_PARSING"
    )
    ai_model_coach: str = Field(
        default="nvidia/nemotron-3.5-lightning:free", alias="AI_MODEL_COACH"
    )
    ai_model_actions: str = Field(
        default="nvidia/nemotron-3.5-lightning:free", alias="AI_MODEL_ACTIONS"
    )
    # Photo food recognition. Separate from the text models because it
    # needs a vision-capable one, and separately switchable because it is
    # the only feature that sends an image anywhere.
    ai_model_vision: str = Field(default="", alias="AI_MODEL_VISION")
    ai_request_timeout_seconds: float = Field(
        default=20.0, alias="AI_REQUEST_TIMEOUT_SECONDS"
    )
    rate_limit_ai_per_hour: int = Field(default=20, alias="RATE_LIMIT_AI_PER_HOUR")
    # Export and account deletion each touch every table the user owns, so
    # they are capped well below the default per-minute allowance.
    rate_limit_account_per_hour: int = Field(
        default=5, alias="RATE_LIMIT_ACCOUNT_PER_HOUR"
    )

    # Food database provider for barcode lookup. Open Food Facts is a free,
    # open-data product database that needs no account or API key -- only a
    # descriptive User-Agent, which their terms require so they can contact
    # heavy API users. Unset -> barcode endpoints return 503 and the rest of
    # the app is unaffected.
    #
    # Opt-in rather than on-by-default: scanning sends the barcode to a third
    # party, and a privacy-first app should not start making outbound requests
    # about what a user eats without the operator explicitly turning it on.
    food_db_provider: str = Field(default="", alias="FOOD_DB_PROVIDER")
    food_db_api_key: str = Field(default="", alias="FOOD_DB_API_KEY")
    food_db_base_url: str = Field(
        default="https://world.openfoodfacts.org", alias="FOOD_DB_BASE_URL"
    )
    food_db_request_timeout_seconds: float = Field(
        default=10.0, alias="FOOD_DB_REQUEST_TIMEOUT_SECONDS"
    )
    food_db_user_agent: str = Field(
        default="Fitora/0.1 (https://github.com/Fahad28may/Fitora)",
        alias="FOOD_DB_USER_AGENT",
    )
    rate_limit_barcode_per_hour: int = Field(
        default=120, alias="RATE_LIMIT_BARCODE_PER_HOUR"
    )

    # Object storage for progress photos. S3-compatible; MinIO is the reference
    # provider (self-hosted, so photos never leave your infrastructure). Same
    # code works against AWS S3 / R2 / B2 by pointing the endpoint elsewhere.
    # Unset -> photo endpoints return 503 and the rest of the app is unaffected.
    s3_endpoint_url: str = Field(default="", alias="S3_ENDPOINT_URL")
    s3_bucket: str = Field(default="", alias="S3_BUCKET")
    s3_access_key_id: str = Field(default="", alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="", alias="S3_SECRET_ACCESS_KEY")
    s3_presigned_url_expiry_seconds: int = Field(
        default=900, alias="S3_PRESIGNED_URL_EXPIRY_SECONDS"
    )

    @property
    def rate_limit_storage_uri(self) -> str:
        """Where rate-limit counters live.

        In-memory counters are per-process, so on any multi-instance
        deployment (serverless especially) a "5 logins per minute" limit
        becomes 5 per minute *per instance* — brute-force protection that
        weakens exactly as the platform scales up under load. Redis makes the
        counters shared. Falls back to memory when unset, which is right for
        local dev and tests and is warned about at startup in production.
        """
        return self.redis_url or "memory://"

    @property
    def rate_limiting_is_shared(self) -> bool:
        return bool(self.redis_url)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key)

    @property
    def vision_enabled(self) -> bool:
        """Photo recognition needs both a key and an explicitly chosen
        vision model. Left off unless an operator opts in: it is the only
        feature that sends a user's photograph to a third party."""
        return bool(self.ai_api_key and self.ai_model_vision)

    @property
    def food_db_enabled(self) -> bool:
        return bool(self.food_db_provider)

    @property
    def storage_enabled(self) -> bool:
        return bool(
            self.s3_endpoint_url
            and self.s3_bucket
            and self.s3_access_key_id
            and self.s3_secret_access_key
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
