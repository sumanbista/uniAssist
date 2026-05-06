"""Academic calendar query tool."""

from typing import Any

from app.core.config import settings
from app.core.constants import ROLE_PUBLIC, TOOL_CALENDAR_QUERY
from app.core.logging import get_logger
from app.tools.base_json_tool import BaseJsonTool

logger = get_logger(__name__)


class CalendarQueryTool(BaseJsonTool):
    """Find academic dates by term, category, or holiday flag."""

    name = TOOL_CALENDAR_QUERY
    description = "Find academic calendar dates by term, category, or holiday."
    allowed_roles = [ROLE_PUBLIC]
    source_file = settings.CALENDAR_DATA_FILE
    last_updated = "2026-01-10"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute an academic calendar query."""

        logger.info("Tool executed: %s with params: %s", self.name, params)
        term_query = self.normalize_text(params.get("term"))
        category_query = self.normalize_text(params.get("category"))
        holiday_query = params.get("holiday")

        if not term_query and not category_query and holiday_query is None:
            return self.error_response("Provide term, category, or holiday to search calendar dates.")

        try:
            records = self.load_records()
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Tool error: %s failed with %s", self.name, exc)
            return self.error_response("Calendar data is unavailable.")

        results = [
            record
            for record in records
            if self._matches_calendar_record(record, term_query, category_query, holiday_query)
        ]
        return self.success_response({"results": results, "count": len(results)})

    def _matches_calendar_record(
        self,
        record: dict[str, Any],
        term_query: str,
        category_query: str,
        holiday_query: Any,
    ) -> bool:
        """Return whether a calendar record matches all provided filters."""

        term_matches = not term_query or term_query in self.normalize_text(record.get("term"))
        category_matches = not category_query or category_query in self.normalize_text(record.get("category"))
        holiday_matches = holiday_query is None or bool(record.get("is_holiday")) == bool(holiday_query)
        return term_matches and category_matches and holiday_matches
