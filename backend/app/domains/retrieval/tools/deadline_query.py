"""Academic deadline query tool."""

from typing import Any

from app.core.config import settings
from app.core.constants import ROLE_ADMIN, ROLE_STUDENT, TOOL_DEADLINE_QUERY
from app.core.logging import get_logger
from app.domains.retrieval.tools.base_json_tool import BaseJsonTool

logger = get_logger(__name__)


class DeadlineQueryTool(BaseJsonTool):
    """Find deadlines by type and term."""

    name = TOOL_DEADLINE_QUERY
    description = "Find academic deadlines by deadline type and term."
    allowed_roles = [ROLE_STUDENT, ROLE_ADMIN]
    source_file = settings.DEADLINES_DATA_FILE
    last_updated = "2026-01-10"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a deadline query."""

        logger.info("Tool executed: %s with params: %s", self.name, params)
        type_query = self.normalize_text(params.get("type"))
        term_query = self.normalize_text(params.get("term"))

        if not type_query and not term_query:
            return self.error_response("Provide a deadline type or term to search deadlines.")

        try:
            deadlines = self.load_records()
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Tool error: %s failed with %s", self.name, exc)
            return self.error_response("Deadline data is unavailable.")

        results = [
            deadline
            for deadline in deadlines
            if self._matches_deadline(deadline, type_query, term_query)
        ]
        return self.success_response({"results": results, "count": len(results)})

    def _matches_deadline(self, deadline: dict[str, Any], type_query: str, term_query: str) -> bool:
        """Return whether a deadline matches all provided filters."""

        deadline_type = self.normalize_text(deadline.get("type"))
        term = self.normalize_text(deadline.get("term"))
        type_matches = not type_query or type_query in deadline_type
        term_matches = not term_query or term_query in term
        return type_matches and term_matches
