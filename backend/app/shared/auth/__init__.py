"""Shared authentication and authorization utilities."""

from app.shared.auth.dependencies import (
    get_current_user,
    require_any_role,
    require_permission,
    require_role,
)
from app.shared.auth.tenant import enforce_university_scope, scoped_university_id

__all__ = [
    "enforce_university_scope",
    "get_current_user",
    "require_any_role",
    "require_permission",
    "require_role",
    "scoped_university_id",
]
