"""Application settings.

`DEPLOYMENT_MODE` is the single switch described in PLAN.md §9. The data model, the RLS
policies and the API surface are identical in both modes; only signup, org resolution,
auth backends and quotas differ.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class DeploymentMode(StrEnum):
    SINGLE_TENANT = "single_tenant"
    SAAS = "saas"


class Environment(StrEnum):
    LOCAL = "local"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DEMARC_",
        env_file=".env",
        extra="ignore",
        secrets_dir="/run/secrets" if Path("/run/secrets").is_dir() else None,
    )

    environment: Environment = Environment.LOCAL
    deployment_mode: DeploymentMode = DeploymentMode.SINGLE_TENANT
    debug: bool = False

    # Identity of this deployment. In single-tenant mode every request resolves to the
    # organization with this slug; in SaaS mode the org comes from the session.
    single_tenant_org_slug: str = "default"

    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://demarc_app:demarc_app@postgres:5432/demarc"  # type: ignore[arg-type]
    )
    redis_url: RedisDsn = Field(default="redis://redis:6379/0")  # type: ignore[arg-type]

    # Object storage (S3-compatible; MinIO locally).
    s3_endpoint_url: str | None = "http://minio:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "demarc-evidence"
    s3_access_key_id: str = "demarc"
    s3_secret_access_key: str = "demarc-dev-secret"

    # 32+ bytes. Signs session cookies. MUST be supplied via secret in production.
    secret_key: str = "dev-only-insecure-key-do-not-use-in-production-0000"

    session_cookie_name: str = "demarc_session"
    session_ttl_hours: int = 12
    session_idle_timeout_minutes: int = 60

    # NoDecode stops pydantic-settings JSON-decoding this before our validator runs, so
    # the env var can be the comma-separated list a human would actually write.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    log_level: str = "INFO"
    log_json: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def is_saas(self) -> bool:
        return self.deployment_mode is DeploymentMode.SAAS

    def validate_for_production(self) -> None:
        """Fail fast rather than run production on development defaults."""
        if not self.is_production:
            return
        problems: list[str] = []
        if "dev-only" in self.secret_key or len(self.secret_key) < 32:
            problems.append("DEMARC_SECRET_KEY must be a unique value of at least 32 bytes")
        if self.debug:
            problems.append("DEMARC_DEBUG must be false in production")
        if self.s3_secret_access_key == "demarc-dev-secret":
            problems.append("DEMARC_S3_SECRET_ACCESS_KEY is still the development default")
        if problems:
            raise RuntimeError("Refusing to start in production: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_for_production()
    return settings
