"""FormatterTools class — registers run_format_code MCP tool."""

import logging
from typing import TYPE_CHECKING

from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.formatter.runner import DEFAULT_STEPS, run_format_code as _run_format_code
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import (
    check_line_length_conflicts,
    resolve_target_directories,
)

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol, ToolServer

logger = logging.getLogger(__name__)


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
            resolved_steps = steps or DEFAULT_STEPS

            # Resolve target directories
            resolved = resolve_target_directories(
                str(self._server.project_dir), target_directories
            )
            if isinstance(resolved, str):
                return resolved
            dirs = resolved

            # Check tool availability upfront
            for step in resolved_steps:
                if not self._server._tool_availability.get(step, False):
                    return (
                        f"Error: {step} is not available in the configured "
                        f"Python environment ({self._server._resolved_python}). "
                        f"Ensure --python-executable and --venv-path point to the "
                        f"environment where {step} is installed. "
                        f"Restart the server after installing."
                    )

            # Check for line-length conflicts
            warnings = check_line_length_conflicts(
                str(self._server.project_dir), resolved_steps
            )

            # Delegate to runner
            try:
                results = _run_format_code(
                    self._server._resolved_python,
                    self._server.project_dir,
                    dirs,
                    resolved_steps,
                    check_only,
                )
            except ValueError as exc:
                return f"Error: {exc}"

            output = _format_results(results, resolved_steps, check_only)
            if warnings:
                output = "\n".join(warnings) + "\n\n" + output
            return output


def _format_results(
    results: dict[str, FormatterResult],
    steps: list[str],
    check_only: bool,
) -> str:
    """Format runner results into markdown output."""
    sections: list[str] = []
    failed_step: str | None = None

    for step in steps:
        if step in results:
            sections.append(f"## {step}\n{results[step].output}")
            if not results[step].success:
                failed_step = step

    if not check_only and failed_step is not None and len(results) < len(steps):
        sections.append(f"\nFormatting stopped due to errors in {failed_step} step.")

    return "\n\n".join(sections)
