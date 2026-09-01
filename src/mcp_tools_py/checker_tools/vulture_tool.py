"""Vulture MCP tool registration."""

import logging
from typing import TYPE_CHECKING, List, Optional

from mcp_tools_py.code_checker_vulture import run_vulture_check as run_vulture
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_target_directories

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.server import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the vulture dead-code checker tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_vulture_check(
        target_directories: Optional[List[str]] = None,
        min_confidence: int = 60,
        extra_args: Optional[List[str]] = None,
    ) -> str:
        """Run vulture on the project to find unused code.

        Args:
            target_directories: Directories to scan relative to project_dir.
                Auto-detected from pyproject.toml when None.
            extra_args: Additional vulture arguments.
            min_confidence: Minimum confidence for reporting (default: 60).

        Returns:
            Raw vulture output (stdout + stderr combined)
        """
        if not server._is_tool_available("vulture"):
            binary_path = server._tool_binaries.get("vulture") or "N/A"
            return (
                f"vulture is not available at {binary_path}. "
                f"Ensure the virtual environment has vulture installed "
                f"and --venv-path is configured. Restart the server after installing."
            )

        resolved = resolve_target_directories(
            str(server.project_dir), target_directories
        )
        if isinstance(resolved, str):
            return resolved

        try:
            logger.info(
                "Starting vulture check",
                extra={
                    "project_dir": str(server.project_dir),
                    "target_directories": resolved,
                    "min_confidence": min_confidence,
                    "extra_args": extra_args,
                },
            )

            project_dir = server.project_dir
            whitelist_path = project_dir / server.vulture_whitelist
            whitelist = str(whitelist_path) if whitelist_path.exists() else None

            output = run_vulture(
                vulture_binary=server._tool_binaries["vulture"],
                project_dir=str(project_dir),
                target_directories=resolved,
                min_confidence=min_confidence,
                extra_args=extra_args,
                whitelist_path=whitelist,
                timeout_seconds=server.resolve_timeout("vulture"),
            )

            logger.info(
                "vulture check completed",
                extra={
                    "output_length": len(output),
                },
            )

            return output

        except Exception as e:
            error_msg = f"Unexpected error running vulture: " f"{type(e).__name__}: {e}"
            logger.error(
                "vulture check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            return error_msg
