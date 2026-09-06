"""Pylint MCP tool registration."""

import logging
from typing import TYPE_CHECKING, List, Optional

from mcp_tools_py.code_checker_pylint import get_pylint_prompt
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_target_directories

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the pylint checker tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_pylint_check(
        extra_args: Optional[List[str]] = None,
        target_directories: Optional[List[str]] = None,
        max_issues: int = 1,
    ) -> str:
        """Run pylint on the project code and generate smart prompts for LLMs.

        Args:
            extra_args: Additional pylint arguments.
            target_directories: Directories to analyze relative to project_dir. Auto-detected from pyproject.toml when None.
            max_issues: Number of issue types to show in detail (default: 1). Remaining issues shown as summary counts.

        Returns:
            Formatted pylint result, or an error message string.
        """
        if not server._is_tool_available("pylint"):
            return server.tool_unavailable_message("pylint")

        resolved = resolve_target_directories(
            str(server.project_dir), target_directories
        )
        if isinstance(resolved, str):
            return resolved

        try:
            resolved_timeout = server.resolve_timeout("pylint")
        except ValueError as exc:
            return f"Error: {exc}"

        try:
            logger.info(
                "Starting pylint check",
                extra={
                    "project_dir": str(server.project_dir),
                    "extra_args": extra_args,
                    "target_directories": resolved,
                    "max_issues": max_issues,
                },
            )

            pylint_prompt = get_pylint_prompt(
                str(server.project_dir),
                python_executable=server._resolved_python,
                extra_args=extra_args,
                target_directories=resolved,
                max_issues=max_issues,
                timeout_seconds=resolved_timeout,
            )

            result = checker_tools._format_pylint_result(pylint_prompt)

            logger.info(
                "Pylint check completed",
                extra={
                    "issues_found": pylint_prompt is not None,
                    "result_length": len(result),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Pylint check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            raise
