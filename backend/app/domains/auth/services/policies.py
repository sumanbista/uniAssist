"""Centralized authorization policy constants."""

from app.domains.auth.models.roles import UserRole

GOVERNANCE_ADMIN_ROLES: frozenset[UserRole] = frozenset(
    {
        UserRole.ADMIN,
        UserRole.UNIVERSITY_ADMIN,
        UserRole.SUPER_ADMIN,
    }
)
