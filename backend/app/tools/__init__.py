"""Structured tools available to the UniAssist router."""

from app.tools.calendar_query import CalendarQueryTool
from app.tools.contact_lookup import ContactLookupTool
from app.tools.deadline_query import DeadlineQueryTool
from app.tools.events_fetch import EventsFetchTool
from app.tools.reg_faq import RegistrationFaqTool

__all__ = [
    "CalendarQueryTool",
    "ContactLookupTool",
    "DeadlineQueryTool",
    "EventsFetchTool",
    "RegistrationFaqTool",
]
