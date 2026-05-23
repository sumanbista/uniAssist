"""Deterministic role and permission authorization checks."""

from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser


class AuthorizationService:
    """Apply least-privilege authorization checks to authenticated users."""

    def has_role(
        self,
        user: AuthenticatedUser,
        allowed_roles: set[UserRole],
    ) -> bool:
        """Return whether the user has one of the allowed roles."""

        return user.role in allowed_roles

    def has_permission(self, user: AuthenticatedUser, permission: str) -> bool:
        """Return whether the user has the required permission."""

        normalized_permission = permission.strip().lower()
        return bool(normalized_permission) and normalized_permission in user.permissions
