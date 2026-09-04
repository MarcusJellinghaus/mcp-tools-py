"""Ruff fix (modifies files) MCP tool registration."""

import logging
from typing import TYPE_CHECKING, List, Optional

from mcp_tools_py.code_checker_ruff.runners import run_ruff_fix_impl
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_target_directories

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.server import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the ruff fix (modifies files) tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_ruff_fix(
        select: Optional[List[str]] = None,
        target_directories: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
    ) -> str:
        """Run ruff check --fix on the project (MODIFIES FILES in-place).

        Only applies safe fixes by default. Pass ["--unsafe-fixes"] via
        extra_args to also apply unsafe fixes.

        Args:
            select: Override rule selection. Defaults to project config.
            target_directories: Directories to fix relative to project_dir. Auto-detected when None.
            extra_args: Additional ruff CLI flags.

        Returns:
            Formatted fix report, or an error message string.
        """
        if not server._is_tool_available("ruff"):
            return server.tool_unavailable_message("ruff")

        resolved = resolve_target_directories(
            str(server.project_dir), target_directories
        )
        if isinstance(resolved, str):
            return resolved

        try:
            logger.info(
                "Starting ruff fix",
                extra={
                    "project_dir": str(server.project_dir),
                    "select": select,
                    "target_directories": resolved,
                    "extra_args": extra_args,
                },
            )

            output = run_ruff_fix_impl(
                ruff_binary=server._tool_binaries["ruff"],
                project_dir=str(server.project_dir),
                target_directories=resolved,
                select=select,
                extra_args=extra_args,
                timeout_seconds=server.resolve_timeout("ruff"),
            )

            logger.info(
                "ruff fix completed",
                extra={"output_length": len(output)},
            )

            return output

        except Exception as e:
            error_msg = (
                f"Unexpected error running ruff fix: " f"{type(e).__name__}: {e}"
            )
            logger.error(
                "ruff fix failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            return error_msg
