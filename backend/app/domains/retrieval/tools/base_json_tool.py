"""Base helpers for tools backed by local JSON datasets."""

from typing import Any

from app.core.logging import get_logger
from app.domains.retrieval.services.data_loader import DataLoader
from app.domains.retrieval.services.tool_interface import Tool

logger = get_logger(__name__)


class BaseJsonTool(Tool):
    """Shared JSON loading and response helpers for structured tools."""

    source_file: str
    last_updated: str

    def __init__(self, data_loader: DataLoader | None = None) -> None:
        self.data_loader = data_loader or DataLoader()

    def success_response(self, data: Any) -> dict[str, Any]:
        """Build a standardized success response."""

        last_updated = self._resolve_last_updated(data)
        return {
            "status": "success",
            "data": data,
            "source": self.source_file,
            "last_updated": last_updated,
        }

    def error_response(self, message: str) -> dict[str, Any]:
        """Build a standardized error response."""

        return {"status": "error", "message": message}

    def load_records(self) -> list[dict[str, Any]]:
        """Load records for this tool from its configured data source."""

        return self.data_loader.load_json(self.source_file)

    def normalize_text(self, value: Any) -> str:
        """Normalize a search parameter for case-insensitive matching."""

        if value is None:
            return ""
        return str(value).strip().lower()

    def _resolve_last_updated(self, data: Any) -> str:
        """Use record-level freshness metadata when available."""

        if not isinstance(data, dict):
            return self.last_updated

        results = data.get("results")
        if not isinstance(results, list) or not results:
            return self.last_updated

        record_dates = [
            str(record["last_updated"])
            for record in results
            if isinstance(record, dict) and record.get("last_updated")
        ]
        return max(record_dates) if record_dates else self.last_updated
