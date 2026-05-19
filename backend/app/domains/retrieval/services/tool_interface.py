"""Abstract interface implemented by all UniAssist tools."""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Standard contract for structured UniAssist tools."""

    name: str
    description: str
    allowed_roles: list[str]

    @abstractmethod
    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool with validated parameters."""
