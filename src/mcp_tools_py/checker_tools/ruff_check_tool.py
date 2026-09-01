"""Ruff check (read-only analysis) MCP tool registration."""

import logging
from typing import TYPE_CHECKING, List, Optional

from mcp_tools_py.code_checker_ruff.runners import run_ruff_check_impl
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_target_directories

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.server import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the ruff check (read-only analysis) tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_ruff_check(
        select: Optional[List[str]] = None,
        target_directories: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
        max_issues: int = 1,
    ) -> str:
        """Run ruff check on the project (read-only analysis).

        Args:
            select: Override rule selection (e.g. ["D", "DOC"]). Defaults to project config.
            target_directories: Directories to check relative to project_dir. Auto-detected when None.
            extra_args: Additional ruff CLI flags (e.g. ["--preview"] for DOC rules).
            max_issues: Number of issue types shown in detail (default: 1).

        Returns:
            Formatted ruff report, or an error message string.
        """
        if not server._is_tool_available("ruff"):
            binary_path = server._tool_binaries.get("ruff") or "N/A"
            return (
                f"ruff is not available at {binary_path}. "
                f"Ensure the virtual environment has ruff installed "
                f"and --venv-path is configured. Restart the server after installing."
            )

        resolved = resolve_target_directories(
            str(server.project_dir), target_directories
        )
        if isinstance(resolved, str):
            return resolved

        try:
            logger.info(
                "Starting ruff check",
                extra={
                    "project_dir": str(server.project_dir),
                    "select": select,
                    "target_directories": resolved,
                    "extra_args": extra_args,
                    "max_issues": max_issues,
                },
            )

            output = run_ruff_check_impl(
                ruff_binary=server._tool_binaries["ruff"],
                project_dir=str(server.project_dir),
                target_directories=resolved,
                select=select,
                extra_args=extra_args,
                max_issues=max_issues,
                timeout_seconds=server.resolve_timeout("ruff"),
            )

            logger.info(
                "ruff check completed",
                extra={"output_length": len(output)},
            )

            return output

        except Exception as e:
            error_msg = (
                f"Unexpected error running ruff check: " f"{type(e).__name__}: {e}"
            )
            logger.error(
                "ruff check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            return error_msg
