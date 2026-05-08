"""Campus events fetching tool."""

from typing import Any

from app.core.config import settings
from app.core.constants import ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT, TOOL_EVENTS_FETCH
from app.core.logging import get_logger
from app.tools.base_json_tool import BaseJsonTool

logger = get_logger(__name__)


class EventsFetchTool(BaseJsonTool):
    """Find campus events by date or category."""

    name = TOOL_EVENTS_FETCH
    description = "Fetch campus events by date or category."
    allowed_roles = [ROLE_STUDENT, ROLE_FACULTY, ROLE_ADMIN]
    source_file = settings.EVENTS_DATA_FILE
    last_updated = "2026-01-10"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute an events search."""

        logger.info("Tool executed: %s with params: %s", self.name, params)
        date_query = self.normalize_text(params.get("date"))
        category_query = self.normalize_text(params.get("category"))

        if not date_query and not category_query:
            return self.error_response("Provide a date or category to fetch events.")

        try:
            events = self.load_records()
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Tool error: %s failed with %s", self.name, exc)
            return self.error_response("Event data is unavailable.")

        results = [
            event
            for event in events
            if self._matches_event(event, date_query, category_query)
        ]
        return self.success_response({"results": results, "count": len(results)})

    def _matches_event(self, event: dict[str, Any], date_query: str, category_query: str) -> bool:
        """Return whether an event matches all provided filters."""

        date_matches = not date_query or date_query == self.normalize_text(event.get("date"))
        category_matches = not category_query or category_query in self.normalize_text(event.get("category"))
        return date_matches and category_matches
