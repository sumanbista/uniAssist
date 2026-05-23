"""Canonical permission names for authorization checks."""

from enum import Enum


class Permission(str, Enum):
    """Supported permission identifiers."""

    FORMS_APPROVE = "forms:approve"
    FORMS_PUBLISH = "forms:publish"
    FORMS_ARCHIVE = "forms:archive"
    GOVERNANCE_REVIEW = "governance:review"
    RELATIONSHIPS_MANAGE = "relationships:manage"
