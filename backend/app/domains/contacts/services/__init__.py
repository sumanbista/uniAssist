"""Contacts service exports."""

from app.domains.contacts.services.contacts_service import (
    ContactsService,
    contact_to_dict,
)

__all__ = ["ContactsService", "contact_to_dict"]
