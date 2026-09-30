"""FormatterTools class — registers run_format_code MCP tool."""

import logging
from typing import TYPE_CHECKING

from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.formatter.runner import resolve_steps
from mcp_tools_py.formatter.runner import run_format_code as _run_format_code
from mcp_tools_py.formatter.runner import step_tool, validate_steps
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import (
    check_line_length_conflicts,
    resolve_target_directories,
)

if TYPE_CHECKING:
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol
    from mcp_tools_py.utils.tool_context import ToolContext

logger = logging.getLogger(__name__)

_UNPARSABLE_CAP = 10


class FormatterTools:
    """Registers formatting tools on an MCP server."""

    def __init__(self, context: "ToolContext") -> None:
        self.context = context

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
            """Run code formatters on the project.

            Args:
                steps: Formatter steps to run in order. Valid values: "isort",
                    "black", "ruff_imports", "ruff_format". When omitted, resolved
                    from pyproject.toml: [tool.mcp-tools-py] formatter = "black"
                    (isort, black) or "ruff" (ruff_imports, ruff_format); else
                    [tool.ruff.format] versus [tool.black]. Both or neither
                    declared is an error, and so is an empty list.
                target_directories: Directories to format relative to project_dir.
                    Defaults to auto-detection from pyproject.toml.
                check_only: If True, only check formatting without modifying files.

            Returns:
                Formatted output with markdown headers per step.
            """
            # Reject unknown steps before they reach the availability check,
            # which would otherwise report them as uninstalled tools.
            try:
                resolved_steps = (
                    resolve_steps(self.context.project_dir) if steps is None else steps
                )
                validate_steps(resolved_steps)
            except ValueError as exc:
                return f"Error: {exc}"

            # Resolve target directories
            resolved = resolve_target_directories(
                str(self.context.project_dir), target_directories
            )
            if isinstance(resolved, str):
                return resolved
            dirs = resolved

            # Check tool availability upfront
            for step in resolved_steps:
                tool = step_tool(step)
                if not self.context.is_tool_available(tool):
                    return f"Error: {self.context.unavailable_message(tool)}"

            # Check for line-length conflicts
            warnings = check_line_length_conflicts(
                str(self.context.project_dir),
                sorted({step_tool(s) for s in resolved_steps}),
            )

            # Delegate to runner
            try:
                timeouts = {
                    step: self.context.resolve_timeout(step_tool(step))
                    for step in resolved_steps
                }
                results = _run_format_code(
                    str(self.context.environment.interpreter),
                    self.context.project_dir,
                    dirs,
                    resolved_steps,
                    check_only,
                    timeouts=timeouts,
                    environment=self.context.tool_environment,
                )
            except ValueError as exc:
                return f"Error: {exc}"

            output = _format_results(results, resolved_steps, check_only)
            if warnings:
                output = "\n".join(warnings) + "\n\n" + output
            return output


def _unparsable_block(step: str, files: list[str]) -> str:
    """Render a warning block for files a formatter could not read.

    Args:
        step: Name of the formatter step that skipped the files.
        files: Paths the formatter reported as unparsable.

    Returns:
        Multi-line warning text, with the listed paths capped at
        `_UNPARSABLE_CAP`. No trailing newline.
    """
    lines = [
        f"ERROR: {step} could not read {len(files)} file(s) - "
        f"they were NOT checked.",
        "A clean result here does NOT mean CI will pass.",
        "The formatter could not parse these files.",
    ]
    lines += [f"  {path}" for path in files[:_UNPARSABLE_CAP]]
    if len(files) > _UNPARSABLE_CAP:
        lines.append(f"  ... and {len(files) - _UNPARSABLE_CAP} more")
    return "\n".join(lines)


def _format_results(
    results: dict[str, FormatterResult],
    steps: list[str],
    check_only: bool,
) -> str:
    """Format runner results into markdown output.

    Returns:
        Markdown report with one `## <step>` section per runner.
    """
    sections: list[str] = []
    failed_step: str | None = None

    for step in steps:
        if step in results:
            body = results[step].output
            if results[step].unparsable_files:
                block = _unparsable_block(step, results[step].unparsable_files)
                body = f"{block}\n{body}"
            sections.append(f"## {step}\n{body}")
            if not results[step].success:
                failed_step = step

    if not check_only and failed_step is not None and len(results) < len(steps):
        sections.append(f"\nFormatting stopped due to errors in {failed_step} step.")

    return "\n\n".join(sections)
