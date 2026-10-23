"""Deptry dependency MCP tool registration."""

import logging
from typing import TYPE_CHECKING

from mcp_tools_py.code_checker_deptry.reporting import format_deptry_report
from mcp_tools_py.code_checker_deptry.runners import run_deptry_check_impl
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_source_directories

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the deptry dependency checker tool."""
    context = checker_tools.context

    @mcp.tool()
    @log_function_call
    def run_deptry_check(
        target_directories: list[str] | None = None,
        extra_args: list[str] | None = None,
        max_issues: int = 1,
        timeout_seconds: int | None = None,
    ) -> str:
        """Run deptry to find missing, unused and misplaced dependencies.

        deptry runs in the project's Python environment and reads the
        project's `[tool.deptry]` configuration.

        Args:
            target_directories: Directories to check relative to project_dir.
                Defaults to the source directories from pyproject.toml,
                excluding test paths.
            extra_args: Additional deptry CLI flags.
                `--json-output`, `--json-output=...` and `-o` are rejected.
            max_issues: Number of issue types shown in detail (default: 1). 0 = counts only: one line per rule
                with count and directory split, no file paths.
            timeout_seconds: Maximum seconds to wait for deptry. Overrides the
                configured limit for this call. Must be a positive integer.
                Defaults to `[tool.mcp-tools-py]` config, then `--check-timeout`,
                then 120.

        Returns:
            Formatted deptry report, or an error message string.
        """
        if not context.is_tool_available("deptry"):
            return context.unavailable_message("deptry")

        resolved = resolve_source_directories(
            str(context.project_dir), target_directories
        )
        if isinstance(resolved, str):
            return resolved

        try:
            resolved_timeout = context.resolve_timeout("deptry", timeout_seconds)
        except ValueError as exc:
            return f"Error: {exc}"

        try:
            logger.info(
                "Starting deptry check",
                extra={
                    "project_dir": str(context.project_dir),
                    "target_directories": resolved,
                    "extra_args": extra_args,
                    "max_issues": max_issues,
                },
            )

            result = run_deptry_check_impl(
                python_executable=str(context.environment.interpreter),
                project_dir=str(context.project_dir),
                target_directories=resolved,
                extra_args=extra_args,
                timeout_seconds=resolved_timeout,
            )

            if result.error:
                return f"deptry error: {result.error}"

            report = format_deptry_report(result.messages, max_issues)

            logger.info(
                "deptry check completed",
                extra={"output_length": len(report) if report else 0},
            )

            return report or "No deptry dependency issues found."

        except Exception as e:
            error_msg = f"Unexpected error running deptry: {type(e).__name__}: {e}"
            logger.error(
                "deptry check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(context.project_dir),
                },
            )
            return error_msg
