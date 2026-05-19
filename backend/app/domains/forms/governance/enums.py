"""Canonical Forms governance enums."""

from enum import StrEnum


class LifecycleStatus(StrEnum):
    """Canonical lifecycle states for governed forms."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    PUBLISHED = "published"
    STALE = "stale"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class VerificationStatus(StrEnum):
    """Canonical verification states for governed forms."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    PUBLISHED = "published"
    STALE = "stale"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    REJECTED = "rejected"
