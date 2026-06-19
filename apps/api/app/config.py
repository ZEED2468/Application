"""Central configuration. All secrets/env flow through here (pydantic-settings)."""

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DOCKER_COMPOSE_HOSTS = frozenset({"postgres", "redis", "bridge"})


def _normalize_asyncpg_url(url: str) -> str:
    """Render/Heroku expose postgres://; SQLAlchemy async needs postgresql+asyncpg://."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Core ---
    environment: str = "development"
    debug: bool = True

    # --- Database ---
    database_url: str = "postgresql+asyncpg://jd:jd@localhost:5432/jd"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Auth ---
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = False
    cookie_domain: str | None = None

    # --- HMAC shared secrets (bridge + webhook signature) ---
    bridge_hmac_secret: str = "dev-bridge-secret"
    resend_webhook_secret: str = "dev-resend-secret"

    # --- Integrations (optional in dev; fakes used when blank) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    resend_api_key: str = ""
    apollo_api_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    serpapi_api_key: str = ""

    # --- R2 / S3 ---
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "jd-cvs"
    r2_endpoint: str = ""

    # --- Bridge ---
    bridge_base_url: str = "http://localhost:8081"

    # --- Email warm-up ---
    weekly_cap_per_hunter: int = 20
    use_fake_integrations: bool = Field(default=True)

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError(
                "DATABASE_URL is required. On Render, create a Postgres database, "
                "link it to this service, and use the Internal Database URL."
            )
        url = _normalize_asyncpg_url(str(value).strip())
        host = urlparse(url).hostname
        if not host:
            raise ValueError(
                "DATABASE_URL has no hostname. Check the connection string in Render "
                "Environment settings."
            )
        return url

    @model_validator(mode="after")
    def reject_compose_hosts_in_production(self) -> "Settings":
        host = urlparse(self.database_url).hostname
        if self.environment == "production" and host in _DOCKER_COMPOSE_HOSTS:
            raise ValueError(
                f"DATABASE_URL host '{host}' is a Docker Compose service name and "
                "cannot be resolved on Render. Use the Internal Database URL from "
                "your Render Postgres instance (e.g. dpg-xxxxx-a.oregon-postgres.render.com)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
