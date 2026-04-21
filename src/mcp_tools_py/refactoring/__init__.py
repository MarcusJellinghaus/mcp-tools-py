"""Python refactoring tools powered by rope and jedi."""

from pathlib import Path
from typing import TYPE_CHECKING

from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.refactoring.jedi_tools import find_references as jedi_find_references
from mcp_tools_py.refactoring.jedi_tools import list_symbols as jedi_list_symbols
from mcp_tools_py.refactoring.rope_tools import move_module as rope_move_module
from mcp_tools_py.refactoring.rope_tools import move_symbol as rope_move_symbol
from mcp_tools_py.refactoring.rope_tools import rename_symbol as rope_rename_symbol

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol


class RefactoringTools:
    """Registers refactoring tools on an MCP server."""

    def __init__(self, project_dir: Path, timeout: int = 120) -> None:
        self._project_dir = project_dir
        self._timeout = timeout

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all refactoring tools."""
        self._register_jedi_tools(mcp)
        self._register_rope_tools(mcp)

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

    def _register_rope_tools(self, mcp: "FastMCPProtocol") -> None:
        """Register rope-based refactoring tools.

        Rope operations run in isolated subprocesses via rope_cli.py,
        using the same pattern as pytest/pylint/mypy runners. This
        avoids blocking the MCP server's event loop and stdio pipes.
        """
        project_dir = self._project_dir
        timeout = self._timeout

        @mcp.tool()
        @log_function_call
        def move_symbol(
            source_file: str,
            symbol_names: list[str],
            dest_file: str,
            dry_run: bool = False,
        ) -> str:
            """Move top-level functions, classes, or variables to another module.
            Updates all imports project-wide. Auto-creates destination file and
            missing __init__.py files if needed.

            Args:
                source_file: Source file path relative to project root.
                symbol_names: Names of top-level symbols to move.
                dest_file: Destination file path relative to project root.
                dry_run: Preview changes without applying (default: False).
            """
            return rope_move_symbol(
                project_dir,
                source_file,
                symbol_names,
                dest_file,
                dry_run,
                timeout=timeout,
            )

        @mcp.tool()
        @log_function_call
        def rename_symbol(
            file: str,
            symbol_name: str,
            new_name: str,
            dry_run: bool = False,
        ) -> str:
            """Rename a module-level symbol and update all references project-wide.

            Args:
                file: File path relative to project root.
                symbol_name: Current name of the symbol.
                new_name: New name for the symbol.
                dry_run: Preview changes without applying (default: False).
            """
            return rope_rename_symbol(
                project_dir,
                file,
                symbol_name,
                new_name,
                dry_run,
                timeout=timeout,
            )

        @mcp.tool()
        @log_function_call
        def move_module(
            source_module: str,
            dest_package: str,
            dry_run: bool = False,
        ) -> str:
            """Move an entire module inside a new package. Updates all references.

            Args:
                source_module: Source module path relative to project root.
                dest_package: Destination package path relative to project root.
                dry_run: Preview changes without applying (default: False).
            """
            return rope_move_module(
                project_dir,
                source_module,
                dest_package,
                dry_run,
                timeout=timeout,
            )
