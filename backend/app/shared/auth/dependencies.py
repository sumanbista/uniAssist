"""Reusable FastAPI authentication and authorization dependencies."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.logging import get_logger
from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import AuthorizationService
from app.shared.auth.errors import forbidden_error, unauthorized_error
from app.shared.auth.jwt import supabase_jwt_verifier

logger = get_logger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)
authorization_service = AuthorizationService()


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    """Validate the bearer token and return the authenticated user."""

    if credentials is None or credentials.scheme.lower() != settings.AUTH_HEADER_SCHEME.lower():
        logger.warning("Authentication failed: bearer credentials missing")
        raise unauthorized_error()
    return supabase_jwt_verifier.verify(credentials.credentials)


def require_role(*allowed_roles: UserRole) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Build a dependency that requires one of the provided roles."""

    allowed_role_set = set(allowed_roles)

    async def dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not authorization_service.has_role(user, allowed_role_set):
            logger.warning(
                "Authorization denied: user_id=%s role=%s required_roles=%s",
                user.user_id,
                user.role.value,
                sorted(role.value for role in allowed_role_set),
            )
            raise forbidden_error()
        return user

    return dependency


def require_any_role(
    allowed_roles: frozenset[UserRole],
) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Build a dependency that requires one role from a centralized policy set."""

    return require_role(*allowed_roles)


def require_permission(permission: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Build a dependency that requires an explicit permission."""

    async def dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not authorization_service.has_permission(user, permission):
            logger.warning(
                "Authorization denied: user_id=%s missing_permission=%s",
                user.user_id,
                permission,
            )
            raise forbidden_error()
        return user

    return dependency
