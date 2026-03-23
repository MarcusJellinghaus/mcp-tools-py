"""Python refactoring tools powered by rope and jedi."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol


class RefactoringTools:
    """Registers refactoring tools on an MCP server."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all refactoring tools. (No tools registered yet.)"""
        pass
