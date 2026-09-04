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

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

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
    ai_request_timeout_seconds: float = Field(
        default=20.0, alias="AI_REQUEST_TIMEOUT_SECONDS"
    )
    rate_limit_ai_per_hour: int = Field(default=20, alias="RATE_LIMIT_AI_PER_HOUR")

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
