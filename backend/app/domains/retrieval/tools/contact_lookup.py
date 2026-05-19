"""Faculty and staff contact lookup tool."""

from typing import Any

from app.core.config import settings
from app.core.constants import ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT, TOOL_CONTACT_LOOKUP
from app.core.logging import get_logger
from app.domains.retrieval.tools.base_json_tool import BaseJsonTool

logger = get_logger(__name__)


class ContactLookupTool(BaseJsonTool):
    """Find faculty or staff by name and department."""

    name = TOOL_CONTACT_LOOKUP
    description = "Find faculty and staff contact information."
    allowed_roles = [ROLE_STUDENT, ROLE_FACULTY, ROLE_ADMIN]
    source_file = settings.CONTACTS_DATA_FILE
    last_updated = "2026-01-10"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a contact lookup using optional name and department filters."""

        logger.info("Tool executed: %s with params: %s", self.name, params)
        name_query = self.normalize_text(params.get("name"))
        department_query = self.normalize_text(params.get("department"))
        role_query = self.normalize_text(params.get("role"))

        if not name_query and not department_query and not role_query:
            return self.error_response("Provide a name, department, or role to search contacts.")

        try:
            contacts = self.load_records()
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Tool error: %s failed with %s", self.name, exc)
            return self.error_response("Contact data is unavailable.")

        results = [
            contact
            for contact in contacts
            if self._matches_contact(contact, name_query, department_query, role_query)
        ]
        return self.success_response({"results": results, "count": len(results)})

    def _matches_contact(
        self,
        contact: dict[str, Any],
        name_query: str,
        department_query: str,
        role_query: str,
    ) -> bool:
        """Return whether a contact matches all provided filters."""

        contact_name = self.normalize_text(contact.get("name"))
        department = self.normalize_text(contact.get("department"))
        role = self.normalize_text(contact.get("role"))
        name_matches = not name_query or name_query in contact_name
        department_matches = not department_query or department_query in department
        role_matches = not role_query or role_query in role
        return name_matches and department_matches and role_matches
