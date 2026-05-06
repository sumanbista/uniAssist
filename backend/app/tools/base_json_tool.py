"""Base helpers for tools backed by local JSON datasets."""

from typing import Any

from app.core.logging import get_logger
from app.services.data_loader import DataLoader
from app.services.tool_interface import Tool

logger = get_logger(__name__)


class BaseJsonTool(Tool):
    """Shared JSON loading and response helpers for structured tools."""

    source_file: str
    last_updated: str

    def __init__(self, data_loader: DataLoader | None = None) -> None:
        self.data_loader = data_loader or DataLoader()

    def success_response(self, data: Any) -> dict[str, Any]:
        """Build a standardized success response."""

        return {
            "status": "success",
            "data": data,
            "source": self.source_file,
            "last_updated": self.last_updated,
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
