"""Format structured tool data into concise user-facing answers."""

from typing import Any

from app.core.constants import (
    TOOL_CALENDAR_QUERY,
    TOOL_CONTACT_LOOKUP,
    TOOL_DEADLINE_QUERY,
    TOOL_EVENTS_FETCH,
    TOOL_REG_FAQ,
)
from app.models.query import RoutingDecision


class ResponseFormatter:
    """Create natural language answers from trusted tool outputs."""

    def format_answer(
        self,
        query: str,
        decision: RoutingDecision,
        tool_result: dict[str, Any],
    ) -> str:
        """Format a concise answer without adding facts outside tool data."""

        data = tool_result.get("data", {})
        results = data.get("results", []) if isinstance(data, dict) else []
        if not results:
            return "I found no matching university records for that request."

        if decision.tool == TOOL_DEADLINE_QUERY:
            return self._format_deadline(results[0])
        if decision.tool == TOOL_CONTACT_LOOKUP:
            return self._format_contact(results[0])
        if decision.tool == TOOL_EVENTS_FETCH:
            return self._format_events(results)
        if decision.tool == TOOL_CALENDAR_QUERY:
            return self._format_calendar(results)
        if decision.tool == TOOL_REG_FAQ:
            return self._format_faq(results[0])
        return "I found matching university records for that request."

    def _format_deadline(self, deadline: dict[str, Any]) -> str:
        """Format a deadline record."""

        return f"{deadline.get('description')} Date: {deadline.get('date')}."

    def _format_contact(self, contact: dict[str, Any]) -> str:
        """Format a contact record."""

        return (
            f"{contact.get('name')} is listed as {contact.get('role')} in "
            f"{contact.get('department')}. Email: {contact.get('email')}. "
            f"Office: {contact.get('office')}. Hours: {contact.get('hours')}."
        )

    def _format_events(self, events: list[dict[str, Any]]) -> str:
        """Format one or more event records."""

        event_summaries = [
            f"{event.get('title')} on {event.get('date')} at {event.get('time')} in {event.get('location')}"
            for event in events[:3]
        ]
        return "Matching events: " + "; ".join(event_summaries) + "."

    def _format_calendar(self, records: list[dict[str, Any]]) -> str:
        """Format one or more calendar records."""

        calendar_summaries = [
            f"{record.get('title')} is on {record.get('date')}"
            for record in records[:3]
        ]
        return "Academic calendar matches: " + "; ".join(calendar_summaries) + "."

    def _format_faq(self, faq: dict[str, Any]) -> str:
        """Format a registration FAQ record."""

        return str(faq.get("answer", "I found a matching FAQ, but it has no answer text."))
