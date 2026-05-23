"""Tenant-aware access enforcement helpers."""

from uuid import UUID

from app.core.logging import get_logger
from app.domains.auth.schemas import AuthenticatedUser
from app.shared.auth.errors import forbidden_error

logger = get_logger(__name__)


def enforce_university_scope(
    user: AuthenticatedUser,
    university_id: UUID,
) -> None:
    """Fail securely when a request attempts cross-university access."""

    if user.university_id != university_id:
        logger.warning(
            "Tenant access denied: user_id=%s user_university_id=%s requested_university_id=%s",
            user.user_id,
            user.university_id,
            university_id,
        )
        raise forbidden_error()


def scoped_university_id(user: AuthenticatedUser, requested_university_id: UUID) -> UUID:
    """Return a verified tenant scope for repository/service queries."""

    enforce_university_scope(user, requested_university_id)
    return requested_university_id
