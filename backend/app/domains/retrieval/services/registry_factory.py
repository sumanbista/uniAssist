"""Factory for the production tool registry."""

from app.domains.retrieval.services.tool_registry import ToolRegistry
from app.domains.retrieval.tools import (
    CalendarQueryTool,
    ContactLookupTool,
    DeadlineQueryTool,
    EventsFetchTool,
    RegistrationFaqTool,
)


def build_tool_registry() -> ToolRegistry:
    """Create a registry with every Phase 1 tool."""

    return ToolRegistry(
        tools=[
            ContactLookupTool(),
            CalendarQueryTool(),
            EventsFetchTool(),
            DeadlineQueryTool(),
            RegistrationFaqTool(),
        ]
    )
