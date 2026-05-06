"""Central registry for all structured tools."""

from typing import Any

from app.models.tool import ToolMetadata
from app.services.tool_interface import Tool


class ToolRegistry:
    """Register and retrieve tools by name."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def list_tools(self) -> list[ToolMetadata]:
        """Return metadata for every registered tool."""

        return [
            ToolMetadata(
                name=tool.name,
                description=tool.description,
                allowed_roles=tool.allowed_roles,
            )
            for tool in self._tools.values()
        ]

    def get_tool(self, tool_name: str) -> Tool | None:
        """Return a tool by name, if it exists."""

        return self._tools.get(tool_name)

    def run_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a registered tool and return a structured response."""

        tool = self.get_tool(tool_name)
        if tool is None:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

        return tool.run(params)
