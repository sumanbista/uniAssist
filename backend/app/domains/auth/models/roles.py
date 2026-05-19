"""Role definitions for UniAssist access control."""

from enum import Enum


class UserRole(str, Enum):
    """Supported user roles for demo RBAC."""

    STUDENT = "student"
    FACULTY = "faculty"
    ADMIN = "admin"


DEFAULT_ROLE = UserRole.STUDENT
