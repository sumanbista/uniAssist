"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend."""

    model_config = SettingsConfigDict(env_prefix="UNIASSIST_")

    APP_NAME: str = "UniAssist AI"
    API_VERSION: str = "0.1.0"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    BASE_DIR: Path = Path(__file__).resolve().parents[1]
    DATA_PATH: Path = BASE_DIR / "data"
    LOG_DB_PATH: Path = DATA_PATH / "query_logs.sqlite3"

    CONTACTS_DATA_FILE: str = "contacts.json"
    CALENDAR_DATA_FILE: str = "calendar.json"
    EVENTS_DATA_FILE: str = "events.json"
    DEADLINES_DATA_FILE: str = "deadlines.json"
    FAQ_DATA_FILE: str = "faq.json"

    SUPABASE_JWT_SECRET: str | None = None
    SUPABASE_JWT_ISSUER: str | None = None
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    AUTH_HEADER_SCHEME: str = "Bearer"


settings = Settings()
