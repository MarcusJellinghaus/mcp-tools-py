"""Tach architecture-boundary MCP tool registration."""

import logging
from typing import TYPE_CHECKING

from mcp_tools_py.code_checker_tach import run_tach_check as run_tach
from mcp_tools_py.log_utils import log_function_call

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.server import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the tach architecture boundary checker tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_tach_check() -> str:
        """Run tach check on the project to validate architectural boundaries.

        Returns:
            Status line followed by raw JSON output from `tach check --output json`.
        """
        if not server._is_tool_available("tach"):
            binary_path = server._tach_binary or "N/A"
            return (
                f"tach is not available at {binary_path}. "
                f"Ensure the virtual environment has tach installed "
                f"and --venv-path is configured. Restart the server after installing."
            )

        try:
            logger.info(
                "Starting tach check",
                extra={"project_dir": str(server.project_dir)},
            )
            binary = server._tach_binary
            assert binary is not None  # guarded by availability check above
            output = run_tach(
                tach_binary=binary,
                project_dir=str(server.project_dir),
                timeout_seconds=server.resolve_timeout("tach"),
            )
            logger.info(
                "tach check completed",
                extra={"output_length": len(output)},
            )
            return output

        except Exception as e:
            error_msg = f"Unexpected error running tach: {type(e).__name__}: {e}"
            logger.error(
                "tach check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            return error_msg
