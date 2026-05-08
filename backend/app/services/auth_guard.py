"""Authorization helpers for role-based tool access."""

from app.models.roles import UserRole
from app.services.tool_interface import Tool


class AccessDeniedError(Exception):
    """Raised when a role is not allowed to execute a tool."""

    def __init__(self, role: UserRole, tool_name: str) -> None:
        self.role = role
        self.tool_name = tool_name
        super().__init__("You do not have permission to access this resource.")


def authorize_tool_access(tool: Tool, role: UserRole) -> None:
    """Validate that the user role can execute the selected tool."""

    if role.value not in tool.allowed_roles:
        raise AccessDeniedError(role=role, tool_name=tool.name)
