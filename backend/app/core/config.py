"""Application settings loaded from environment variables."""

from pathlib import Path
from uuid import UUID

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
    PDF_FORM_STORAGE_ROOT: Path = DATA_PATH / "uploaded_forms"
    PDF_FORM_MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024
    PDF_FORM_TEXT_PREVIEW_CHARS: int = 1000

    CONTACTS_DATA_FILE: str = "contacts.json"
    CALENDAR_DATA_FILE: str = "calendar.json"
    EVENTS_DATA_FILE: str = "events.json"
    DEADLINES_DATA_FILE: str = "deadlines.json"
    FAQ_DATA_FILE: str = "faq.json"

    CALDWELL_UNIVERSITY_ID: UUID = UUID("11111111-1111-4111-8111-111111111111")
    CALDWELL_FORMS_SOURCE_URL: str = "https://www.caldwell.edu/registrar/"
    CALDWELL_CALENDAR_SOURCE_URL: str = (
        "https://my.caldwell.edu/ICS/Calendar.jnz?portlet=Downloadable_Calendars"
    )

    SUPABASE_JWT_SECRET: str | None = None
    SUPABASE_JWT_ISSUER: str | None = None
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    AUTH_HEADER_SCHEME: str = "Bearer"

    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384
    FORMS_FTS_WEIGHT: float = 0.55
    FORMS_SEMANTIC_WEIGHT: float = 0.45
    ORCHESTRATION_ALLOWED_TOOLS: list[str] = [
        "forms_search",
        "semantic_forms_search",
        "relationship_lookup",
        "calendar_query",
        "deadline_query",
    ]
    ORCHESTRATION_MAX_STEPS: int = 3
    ORCHESTRATION_TOOL_TIMEOUT_SECONDS: float = 5.0
    ORCHESTRATION_RESULT_LIMIT: int = 5
    ORCHESTRATION_RELATIONSHIP_LOOKUP_LIMIT: int = 5
    TRAVERSAL_MAX_HOPS: int = 2
    TRAVERSAL_MAX_NODES: int = 25
    TRAVERSAL_TIMEOUT_MS: int = 500
    TRAVERSAL_ALLOWED_RELATIONSHIP_TYPES: list[str] = [
        "requires",
        "deadline_for",
        "related_to",
        "references",
    ]


settings = Settings()
