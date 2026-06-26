"""Supabase-compatible JWT verification."""

from typing import Any
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.shared.auth.errors import unauthorized_error

logger = get_logger(__name__)


class SupabaseJWTVerifier:
    """Verify Supabase JWTs and convert claims into a user context."""

    def verify(self, token: str) -> AuthenticatedUser:
        """Return authenticated user context for a valid JWT."""

        if not token or not settings.SUPABASE_JWT_SECRET:
            logger.warning("Authentication failed: missing token or JWT secret")
            raise unauthorized_error()

        required_claims = ["exp", "sub", "aud"]
        if settings.SUPABASE_JWT_ISSUER is not None:
            required_claims.append("iss")

        try:
            claims = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=settings.SUPABASE_JWT_AUDIENCE,
                issuer=settings.SUPABASE_JWT_ISSUER,
                options={
                    "require": required_claims,
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": settings.SUPABASE_JWT_ISSUER is not None,
                },
            )
            return self._build_user_context(claims)
        except (InvalidTokenError, ValidationError, ValueError) as exc:
            logger.warning("Authentication failed: invalid JWT context: %s", type(exc).__name__)
            raise unauthorized_error() from exc

    def _build_user_context(self, claims: dict[str, Any]) -> AuthenticatedUser:
        """Map verified JWT claims to the canonical user context."""

        app_metadata = _claim_object(claims.get("app_metadata"))
        role = _extract_role(claims, app_metadata)
        university_id = _extract_university_id(claims, app_metadata)
        permissions = _extract_permissions(app_metadata)
        department_scope = app_metadata.get("department_scope")

        if not isinstance(role, str) or not isinstance(university_id, str):
            raise ValueError("required authorization claims are missing")

        return AuthenticatedUser(
            user_id=UUID(str(claims["sub"])),
            university_id=UUID(university_id),
            role=UserRole(role.strip().lower()),
            permissions=permissions,
            department_scope=department_scope if isinstance(department_scope, str) else None,
        )


def _claim_object(value: object) -> dict[str, Any]:
    """Return a JWT claim object if it is a dictionary."""

    if isinstance(value, dict):
        return value
    return {}


def _extract_role(
    claims: dict[str, Any],
    app_metadata: dict[str, Any],
) -> object:
    """Return the UniAssist role from Supabase-compatible claims."""

    authorization = _claim_object(app_metadata.get("authorization"))
    top_level_role = claims.get("uniassist_role") or claims.get("app_role")
    if isinstance(top_level_role, str):
        return top_level_role
    for container in (app_metadata, authorization):
        value = container.get("role")
        if isinstance(value, str) and value != "authenticated":
            return value
    roles = app_metadata.get("roles")
    if isinstance(roles, list):
        for value in roles:
            if isinstance(value, str) and value != "authenticated":
                return value
    claim_role = claims.get("role")
    if isinstance(claim_role, str) and claim_role != "authenticated":
        return claim_role
    return None


def _extract_university_id(
    claims: dict[str, Any],
    app_metadata: dict[str, Any],
) -> object:
    """Return the tenant UUID from supported Supabase metadata locations."""

    authorization = _claim_object(app_metadata.get("authorization"))
    return (
        app_metadata.get("university_id")
        or authorization.get("university_id")
        or claims.get("university_id")
    )


def _extract_permissions(app_metadata: dict[str, Any]) -> list[str]:
    """Return string permissions from Supabase metadata."""

    value = app_metadata.get("permissions") or []
    if not isinstance(value, list):
        return []
    return [permission for permission in value if isinstance(permission, str)]


supabase_jwt_verifier = SupabaseJWTVerifier()
