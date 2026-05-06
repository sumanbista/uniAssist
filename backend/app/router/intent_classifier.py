"""Intent classifier that converts user text into a tool decision."""

from __future__ import annotations

import string
from datetime import date, timedelta
from typing import Any

from app.core.constants import (
    TOOL_CALENDAR_QUERY,
    TOOL_CONTACT_LOOKUP,
    TOOL_DEADLINE_QUERY,
    TOOL_EVENTS_FETCH,
    TOOL_REG_FAQ,
)
from app.core.logging import get_logger
from app.models.query import RoutingDecision

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You classify university information requests into exactly one structured tool.
Return only JSON with keys: tool, parameters, confidence.

Available tools:
- contact_lookup: faculty or staff contact info
- calendar_query: academic calendar dates, terms, holidays, breaks
- events_fetch: campus events by date or category
- deadline_query: academic deadlines by type or term
- reg_faq: registration how-to questions

Few-shot examples:
Query: "When is add/drop deadline?"
Output:
{"tool":"deadline_query","parameters":{"type":"add_drop"},"confidence":0.95}

Query: "Who is the dean of engineering?"
Output:
{"tool":"contact_lookup","parameters":{"role":"dean","department":"engineering"},"confidence":0.93}

Query: "How do I register for classes?"
Output:
{"tool":"reg_faq","parameters":{"query":"register classes"},"confidence":0.94}
"""


class IntentClassifier:
    """Classify user queries into tool routing decisions."""

    def classify(self, query: str) -> RoutingDecision:
        """Return a structured routing decision for the query."""

        normalized_query = query.strip().lower()
        logger.info("Classifying query: %s", query)

        if not normalized_query:
            return RoutingDecision(tool="", parameters={}, confidence=0.0)

        return self._classify_with_rules(normalized_query)

    def _classify_with_rules(self, query: str) -> RoutingDecision:
        """Classify common Sprint 2 intents with deterministic local rules."""

        if self._contains_any(query, ["deadline", "add/drop", "add drop", "withdraw", "graduation"]):
            return RoutingDecision(
                tool=TOOL_DEADLINE_QUERY,
                parameters=self._deadline_parameters(query),
                confidence=0.94,
            )

        if self._contains_any(query, ["event", "workshop", "fair", "showcase", "lab", "campus"]):
            return RoutingDecision(
                tool=TOOL_EVENTS_FETCH,
                parameters=self._event_parameters(query),
                confidence=0.9,
            )

        if self._contains_any(query, ["register", "registration", "waitlist", "hold", "swap", "section"]):
            return RoutingDecision(
                tool=TOOL_REG_FAQ,
                parameters={"query": self._clean_query(query)},
                confidence=0.91,
            )

        if self._contains_any(query, ["calendar", "holiday", "break", "first day", "last day", "classes start"]):
            return RoutingDecision(
                tool=TOOL_CALENDAR_QUERY,
                parameters=self._calendar_parameters(query),
                confidence=0.88,
            )

        if self._contains_any(query, ["who is", "email", "office", "advisor", "professor", "chair", "dean", "contact"]):
            return RoutingDecision(
                tool=TOOL_CONTACT_LOOKUP,
                parameters=self._contact_parameters(query),
                confidence=0.87,
            )

        return RoutingDecision(tool="", parameters={}, confidence=0.2)

    def _deadline_parameters(self, query: str) -> dict[str, Any]:
        """Extract deadline parameters from normalized query text."""

        params: dict[str, Any] = {}
        if self._contains_any(query, ["add/drop", "add drop", "drop", "add"]):
            params["type"] = "add_drop"
        elif "withdraw" in query:
            params["type"] = "withdrawal"
        elif "graduation" in query:
            params["type"] = "graduation_application"

        term = self._extract_term(query)
        if term:
            params["term"] = term
        return params

    def _event_parameters(self, query: str) -> dict[str, Any]:
        """Extract event parameters from normalized query text."""

        params: dict[str, Any] = {}
        event_date = self._extract_relative_date(query)
        if event_date:
            params["date"] = event_date
        for category in ["career", "academic", "registration", "wellness"]:
            if category in query:
                params["category"] = category
        if not params:
            params["category"] = "registration" if "registration" in query else "academic"
        return params

    def _calendar_parameters(self, query: str) -> dict[str, Any]:
        """Extract academic calendar parameters from normalized query text."""

        params: dict[str, Any] = {}
        term = self._extract_term(query)
        if term:
            params["term"] = term
        if "holiday" in query:
            params["holiday"] = True
        elif "break" in query:
            params["category"] = "break"
        elif self._contains_any(query, ["first day", "last day", "classes start"]):
            params["category"] = "term"
        return params

    def _contact_parameters(self, query: str) -> dict[str, Any]:
        """Extract contact lookup parameters from normalized query text."""

        params: dict[str, Any] = {}
        department_map = {
            "cs": "computer science",
            "computer science": "computer science",
            "engineering": "engineering",
            "biology": "biology",
            "registrar": "registrar",
            "financial aid": "financial aid",
        }
        for keyword, department in department_map.items():
            if keyword in query:
                params["department"] = department
                break

        for role in ["advisor", "professor", "chair", "dean", "counselor"]:
            if role in query:
                params["role"] = role
                break
        return params

    def _extract_term(self, query: str) -> str | None:
        """Extract a supported academic term from query text."""

        for season in ["spring", "summer", "fall", "winter"]:
            if season in query:
                year = "2026"
                words = query.split()
                for word in words:
                    if word.isdigit() and len(word) == 4:
                        year = word
                return f"{season.title()} {year}"
        return None

    def _extract_relative_date(self, query: str) -> str | None:
        """Extract simple relative dates for event queries."""

        today = date.today()
        if "tomorrow" in query:
            return (today + timedelta(days=1)).isoformat()
        if "today" in query:
            return today.isoformat()
        return None

    def _clean_query(self, query: str) -> str:
        """Remove filler words while preserving useful FAQ keywords."""

        filler_words = {"how", "do", "i", "what", "should", "if", "a", "the", "for", "to"}
        words = [
            word.strip(string.punctuation)
            for word in query.split()
        ]
        return " ".join(word for word in words if word and word not in filler_words)

    def _contains_any(self, query: str, keywords: list[str]) -> bool:
        """Return whether the query contains any listed keyword."""

        return any(keyword in query for keyword in keywords)
