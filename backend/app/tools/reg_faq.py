"""Registration FAQ search tool."""

from typing import Any

from app.core.config import settings
from app.core.constants import ROLE_PUBLIC, TOOL_REG_FAQ
from app.core.logging import get_logger
from app.tools.base_json_tool import BaseJsonTool

logger = get_logger(__name__)


class RegistrationFaqTool(BaseJsonTool):
    """Find registration FAQ answers by keyword."""

    name = TOOL_REG_FAQ
    description = "Find answers to registration frequently asked questions."
    allowed_roles = [ROLE_PUBLIC]
    source_file = settings.FAQ_DATA_FILE
    last_updated = "2026-01-10"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a keyword FAQ search."""

        logger.info("Tool executed: %s with params: %s", self.name, params)
        query = self.normalize_text(params.get("query") or params.get("keyword"))

        if not query:
            return self.error_response("Provide a query or keyword to search registration FAQs.")

        try:
            faqs = self.load_records()
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Tool error: %s failed with %s", self.name, exc)
            return self.error_response("FAQ data is unavailable.")

        results = [faq for faq in faqs if self._matches_faq(faq, query)]
        return self.success_response({"results": results, "count": len(results)})

    def _matches_faq(self, faq: dict[str, Any], query: str) -> bool:
        """Return whether an FAQ contains the query in searchable fields."""

        searchable_text = " ".join(
            [
                self.normalize_text(faq.get("question")),
                self.normalize_text(faq.get("answer")),
                self.normalize_text(" ".join(faq.get("keywords", []))),
            ]
        )
        return query in searchable_text
