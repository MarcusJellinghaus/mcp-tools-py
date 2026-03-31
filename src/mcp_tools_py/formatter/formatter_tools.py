"""FormatterTools class — registers run_format_code MCP tool."""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from mcp_tools_py.formatter.black_runner import run_black
from mcp_tools_py.formatter.isort_runner import run_isort
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_target_directories

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol, ToolServer

logger = logging.getLogger(__name__)

_VALID_STEPS = {"isort", "black"}

_STEP_RUNNERS: dict[str, Callable[..., tuple[str, bool]]] = {
    "isort": run_isort,
    "black": run_black,
}


class FormatterTools:
    """Registers formatting tools on an MCP server."""

    def __init__(self, server: "ToolServer") -> None:
        self._server = server

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all formatter tools with the MCP server."""
        self._register_format_code(mcp)

    def _register_format_code(self, mcp: "FastMCPProtocol") -> None:
        @mcp.tool()
        @log_function_call
        def run_format_code(
            steps: list[str] | None = None,
            target_directories: list[str] | None = None,
            check_only: bool = False,
        ) -> str:
            """Run code formatters (black, isort) on the project.

            Args:
                steps: Formatter steps to run in order. Defaults to ["isort", "black"].
                    Valid values: "isort", "black".
                target_directories: Directories to format relative to project_dir.
                    Defaults to auto-detection from pyproject.toml.
                check_only: If True, only check formatting without modifying files.

            Returns:
                Formatted output with markdown headers per step.
            """
            resolved_steps = steps or ["isort", "black"]

            # Validate step names
            invalid = [s for s in resolved_steps if s not in _VALID_STEPS]
            if invalid:
                return (
                    f"Error: Invalid formatter steps: {invalid}. "
                    f"Valid steps are: {sorted(_VALID_STEPS)}"
                )

            # Resolve target directories
            resolved = resolve_target_directories(
                str(self._server.project_dir), target_directories
            )
            if isinstance(resolved, str):
                return resolved
            dirs = resolved

            sections: list[str] = []
            for step in resolved_steps:
                # Check tool availability
                if not self._server._tool_availability.get(step, False):
                    sections.append(
                        f"Error: {step} is not available in the configured "
                        f"Python environment ({self._server._resolved_python}). "
                        f"Ensure --python-executable and --venv-path point to the "
                        f"environment where {step} is installed. "
                        f"Restart the server after installing."
                    )
                    return _join_sections(sections)

                runner = _STEP_RUNNERS[step]
                output, success = runner(
                    self._server._resolved_python,
                    dirs,
                    str(self._server.project_dir),
                    check_only,
                )

                sections.append(f"## {step}\n{output}")

                if not success and not check_only:
                    sections.append(
                        f"\nFormatting stopped due to errors in {step} step."
                    )
                    return _join_sections(sections)

            return _join_sections(sections)


def _join_sections(sections: list[str]) -> str:
    """Join output sections with double newlines."""
    return "\n\n".join(sections)
