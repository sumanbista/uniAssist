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
        user_metadata = _claim_object(claims.get("user_metadata"))
        role = app_metadata.get("role") or user_metadata.get("role")
        university_id = app_metadata.get("university_id") or user_metadata.get("university_id")
        permissions = app_metadata.get("permissions") or user_metadata.get("permissions") or []
        department_scope = (
            app_metadata.get("department_scope") or user_metadata.get("department_scope")
        )

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


supabase_jwt_verifier = SupabaseJWTVerifier()
