"""SQLite connection and schema utilities for query telemetry."""

import sqlite3
from pathlib import Path

from app.core.config import settings


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with row dictionaries enabled."""

    database_path = db_path or settings.LOG_DB_PATH
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_logging_db(db_path: Path | None = None) -> None:
    """Create telemetry tables when they do not already exist."""

    with get_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                tool_used TEXT,
                role TEXT,
                confidence REAL,
                latency_ms INTEGER,
                fallback_triggered BOOLEAN,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
