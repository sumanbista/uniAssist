"""Shared constants for UniAssist AI."""

from typing import Final

ROLE_PUBLIC: Final[str] = "public"

TOOL_CONTACT_LOOKUP: Final[str] = "contact_lookup"
TOOL_CALENDAR_QUERY: Final[str] = "calendar_query"
TOOL_EVENTS_FETCH: Final[str] = "events_fetch"
TOOL_DEADLINE_QUERY: Final[str] = "deadline_query"
TOOL_REG_FAQ: Final[str] = "reg_faq"

ALL_TOOL_NAMES: Final[tuple[str, ...]] = (
    TOOL_CONTACT_LOOKUP,
    TOOL_CALENDAR_QUERY,
    TOOL_EVENTS_FETCH,
    TOOL_DEADLINE_QUERY,
    TOOL_REG_FAQ,
)
