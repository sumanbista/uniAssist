"""Authenticated principal schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.auth.models.roles import UserRole


class AuthenticatedUser(BaseModel):
    """Canonical authenticated user context for request authorization."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    university_id: UUID
    role: UserRole
    permissions: frozenset[str] = Field(default_factory=frozenset)
    department_scope: str | None = Field(default=None, max_length=100)

    @field_validator("permissions", mode="before")
    @classmethod
    def normalize_permissions(cls, value: object) -> frozenset[str]:
        """Normalize permission claims into a unique immutable set."""

        if value is None:
            return frozenset()
        if not isinstance(value, (list, set, tuple, frozenset)):
            raise ValueError("permissions must be a list")
        normalized_permissions: set[str] = set()
        for permission in value:
            if not isinstance(permission, str):
                raise ValueError("permissions must contain strings")
            normalized_permission = permission.strip().lower()
            if normalized_permission:
                normalized_permissions.add(normalized_permission)
        return frozenset(normalized_permissions)

    @field_validator("department_scope")
    @classmethod
    def normalize_department_scope(cls, value: str | None) -> str | None:
        """Normalize optional department scope."""

        if value is None:
            return None
        normalized_value = value.strip().lower()
        return normalized_value or None
