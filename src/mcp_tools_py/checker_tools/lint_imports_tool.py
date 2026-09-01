"""Lint-imports MCP tool registration."""

import logging
from typing import TYPE_CHECKING, List, Optional

from mcp_tools_py.code_checker_lint_imports import (
    run_lint_imports_check_impl,
)
from mcp_tools_py.log_utils import log_function_call

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.server import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the lint-imports checker tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_lint_imports_check(
        extra_args: Optional[List[str]] = None,
    ) -> str:
        """Run lint-imports on the project to check import contracts.

        Args:
            extra_args: Additional lint-imports arguments.
                Examples: ["--contract", "layers"], ["--verbose"]

        Returns:
            Structured report. The first non-empty line is the state
            header (PASSED / BROKEN / ERROR), so truncation cannot hide
            failures.
        """
        if not server._is_tool_available("lint-imports"):
            return server.tool_unavailable_message("lint-imports")

        try:
            return run_lint_imports_check_impl(
                server._tool_binaries["lint-imports"],
                str(server.project_dir),
                extra_args,
                server.resolve_timeout("lint-imports"),
            )
        except Exception as e:
            error_msg = (
                f"Unexpected error running lint-imports: " f"{type(e).__name__}: {e}"
            )
            logger.error(
                "lint-imports check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            return error_msg
