"""Database configuration for shared infrastructure."""

from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Environment-driven database settings.

    Supabase provides a Postgres connection string. The application normalizes
    that value for SQLAlchemy's async driver while keeping Alembic usable.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        case_sensitive=True,
    )

    SUPABASE_DB_URL: SecretStr | None = Field(default=None)
    SUPABASE_ANON_KEY: SecretStr | None = Field(default=None)
    SUPABASE_SERVICE_ROLE_KEY: SecretStr | None = Field(default=None)
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=30)
    DB_ECHO_SQL: bool = Field(default=False)

    @field_validator(
        "SUPABASE_DB_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        mode="before",
    )
    @classmethod
    def blank_secret_as_none(cls, value: str | None) -> str | None:
        """Treat empty environment values as missing configuration."""

        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_pool_settings(self) -> Self:
        """Validate connection pool settings before engine creation."""

        if self.DB_POOL_SIZE < 1:
            raise ValueError("DB_POOL_SIZE must be at least 1")
        if self.DB_MAX_OVERFLOW < 0:
            raise ValueError("DB_MAX_OVERFLOW cannot be negative")
        if self.DB_POOL_TIMEOUT_SECONDS < 1:
            raise ValueError("DB_POOL_TIMEOUT_SECONDS must be at least 1")
        return self

    @property
    def is_configured(self) -> bool:
        """Return whether a database URL is available."""

        return self.SUPABASE_DB_URL is not None

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return an async SQLAlchemy URL for Supabase Postgres."""

        if self.SUPABASE_DB_URL is None:
            raise RuntimeError("SUPABASE_DB_URL is not configured")
        return normalize_postgres_url(self.SUPABASE_DB_URL.get_secret_value())


def normalize_postgres_url(database_url: str) -> str:
    """Normalize Postgres URLs for SQLAlchemy's asyncpg dialect."""

    stripped_url = database_url.strip()
    if stripped_url.startswith("postgresql+asyncpg://"):
        return stripped_url
    if stripped_url.startswith("postgres://"):
        return stripped_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if stripped_url.startswith("postgresql://"):
        return stripped_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return stripped_url


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Return cached database settings."""

    return DatabaseSettings()
