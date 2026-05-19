"""Analytics aggregation service for query telemetry."""

from pathlib import Path
from typing import Any

from app.shared.observability.db import get_connection, initialize_logging_db


class AnalyticsService:
    """Compute lightweight analytics from persisted query logs."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path
        initialize_logging_db(db_path)

    def summary(self) -> dict[str, Any]:
        """Return high-level query analytics."""

        with get_connection(self.db_path) as connection:
            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_queries,
                    COALESCE(AVG(latency_ms), 0) AS average_latency_ms,
                    COALESCE(SUM(fallback_triggered), 0) AS fallback_count
                FROM query_logs
                """
            ).fetchone()
            most_used_tool = connection.execute(
                """
                SELECT tool_used
                FROM query_logs
                WHERE tool_used IS NOT NULL
                GROUP BY tool_used
                ORDER BY COUNT(*) DESC, tool_used ASC
                LIMIT 1
                """
            ).fetchone()

        total_queries = int(totals["total_queries"])
        fallback_count = int(totals["fallback_count"])
        fallback_rate = fallback_count / total_queries if total_queries else 0.0
        return {
            "total_queries": total_queries,
            "average_latency_ms": round(float(totals["average_latency_ms"])),
            "fallback_count": fallback_count,
            "fallback_rate": round(fallback_rate, 4),
            "most_used_tool": most_used_tool["tool_used"] if most_used_tool else None,
        }

    def tool_counts(self) -> dict[str, int]:
        """Return tool usage counts keyed by tool name."""

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT tool_used, COUNT(*) AS count
                FROM query_logs
                WHERE tool_used IS NOT NULL
                GROUP BY tool_used
                ORDER BY count DESC, tool_used ASC
                """
            ).fetchall()
        return {str(row["tool_used"]): int(row["count"]) for row in rows}

    def role_counts(self) -> dict[str, int]:
        """Return query counts by role."""

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT role, COUNT(*) AS count
                FROM query_logs
                WHERE role IS NOT NULL
                GROUP BY role
                ORDER BY count DESC, role ASC
                """
            ).fetchall()
        return {str(row["role"]): int(row["count"]) for row in rows}

    def recent_queries(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent query log rows for admin inspection."""

        safe_limit = max(1, min(limit, 100))
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    query,
                    request_id,
                    tool_used,
                    role,
                    confidence,
                    latency_ms,
                    fallback_triggered,
                    status,
                    created_at
                FROM query_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "query": row["query"],
                "request_id": row["request_id"],
                "tool_used": row["tool_used"],
                "role": row["role"],
                "confidence": float(row["confidence"] or 0),
                "latency_ms": int(row["latency_ms"] or 0),
                "fallback_triggered": bool(row["fallback_triggered"]),
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
