"""Bandit security MCP tool registration."""

import logging
from typing import TYPE_CHECKING, List, Optional

from mcp_tools_py.code_checker_bandit.reporting import format_bandit_report
from mcp_tools_py.code_checker_bandit.runners import run_bandit_check_impl
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_target_directories

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.server import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the bandit security checker tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_bandit_check(
        target_directories: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
        max_issues: int = 1,
    ) -> str:
        """Run bandit security linter on the project code.

        Args:
            target_directories: Directories to analyze relative to project_dir.
                Auto-detected from pyproject.toml when None.
            extra_args: Additional bandit CLI flags.
            max_issues: Number of issue types to show in detail (default: 1).
                Remaining issues shown as summary counts.

        Returns:
            Formatted bandit report, or an error message string.
        """
        if not server._is_tool_available("bandit"):
            return server.tool_unavailable_message("bandit")

        resolved = resolve_target_directories(
            str(server.project_dir), target_directories
        )
        if isinstance(resolved, str):
            return resolved

        try:
            logger.info(
                "Starting bandit check",
                extra={
                    "project_dir": str(server.project_dir),
                    "target_directories": resolved,
                    "extra_args": extra_args,
                    "max_issues": max_issues,
                },
            )

            result = run_bandit_check_impl(
                bandit_binary=server._tool_binaries["bandit"],
                project_dir=str(server.project_dir),
                target_directories=resolved,
                extra_args=extra_args,
                timeout_seconds=server.resolve_timeout("bandit"),
            )

            if result.error:
                return f"bandit error: {result.error}"

            report = format_bandit_report(result.messages, result.errors, max_issues)

            logger.info(
                "bandit check completed",
                extra={"output_length": len(report) if report else 0},
            )

            return report or "No bandit security issues found."

        except Exception as e:
            error_msg = f"Unexpected error running bandit: {type(e).__name__}: {e}"
            logger.error(
                "bandit check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            return error_msg
