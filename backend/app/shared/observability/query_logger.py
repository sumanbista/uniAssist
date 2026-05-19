"""Query logging service backed by SQLite."""

import sqlite3
from pathlib import Path

from app.core.logging import get_logger
from app.shared.observability.db import get_connection, initialize_logging_db
from app.shared.observability.models import QueryLogRecord

logger = get_logger(__name__)


class QueryLogger:
    """Persist query execution telemetry."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path
        initialize_logging_db(db_path)

    def write(self, record: QueryLogRecord) -> None:
        """Persist a query log record without raising to callers."""

        try:
            with get_connection(self.db_path) as connection:
                connection.execute(
                    """
                    INSERT INTO query_logs (
                        query,
                        request_id,
                        tool_used,
                        role,
                        confidence,
                        latency_ms,
                        fallback_triggered,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.query,
                        record.request_id,
                        record.tool_used,
                        record.role,
                        record.confidence,
                        record.latency_ms,
                        int(record.fallback_triggered),
                        record.status,
                    ),
                )
        except sqlite3.Error as exc:
            logger.error("Failed to write query log: %s", exc)
