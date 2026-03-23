"""Python refactoring tools powered by rope and jedi."""

from pathlib import Path
from typing import TYPE_CHECKING

from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.refactoring.jedi_tools import find_references as jedi_find_references
from mcp_tools_py.refactoring.jedi_tools import list_symbols as jedi_list_symbols

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol


class RefactoringTools:
    """Registers refactoring tools on an MCP server."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all refactoring tools."""
        self._register_jedi_tools(mcp)

    def _register_jedi_tools(self, mcp: "FastMCPProtocol") -> None:
        """Register jedi-based symbol discovery tools."""
        project_dir = self._project_dir

        @mcp.tool()
        @log_function_call
        def list_symbols(file: str) -> str:
            """List all top-level symbols (functions, classes, variables) in a Python file.

            Args:
                file: File path relative to project root.
            """
            return jedi_list_symbols(project_dir, file)

        @mcp.tool()
        @log_function_call
        def find_references(file: str, symbol_name: str) -> str:
            """Find all references to a symbol across the project.

            Args:
                file: File path relative to project root.
                symbol_name: Name of the top-level symbol to find.
            """
            return jedi_find_references(project_dir, file, symbol_name)
