"""Role definitions for UniAssist access control."""

from enum import Enum


class UserRole(str, Enum):
    """Supported user roles for RBAC."""

    STUDENT = "student"
    FACULTY = "faculty"
    DEPARTMENT_ADMIN = "department_admin"
    UNIVERSITY_ADMIN = "university_admin"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


DEFAULT_ROLE = UserRole.STUDENT
