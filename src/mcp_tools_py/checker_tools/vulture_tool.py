"""Vulture MCP tool registration."""

import logging
from typing import TYPE_CHECKING, List, Optional

from mcp_tools_py.code_checker_vulture import run_vulture_check as run_vulture
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import resolve_target_directories

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the vulture dead-code checker tool."""
    context = checker_tools.context

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
        vulture_binary = context.environment.binary("vulture")
        if not context.is_tool_available("vulture") or vulture_binary is None:
            return context.unavailable_message("vulture")

        resolved = resolve_target_directories(
            str(context.project_dir), target_directories
        )
        if isinstance(resolved, str):
            return resolved

        try:
            logger.info(
                "Starting vulture check",
                extra={
                    "project_dir": str(context.project_dir),
                    "target_directories": resolved,
                    "min_confidence": min_confidence,
                    "extra_args": extra_args,
                },
            )

            project_dir = context.project_dir
            whitelist_path = project_dir / context.vulture_whitelist
            whitelist = str(whitelist_path) if whitelist_path.exists() else None

            output = run_vulture(
                vulture_binary=str(vulture_binary),
                project_dir=str(project_dir),
                target_directories=resolved,
                min_confidence=min_confidence,
                extra_args=extra_args,
                whitelist_path=whitelist,
                timeout_seconds=context.resolve_timeout("vulture"),
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
                    "project_dir": str(context.project_dir),
                },
            )
            return error_msg
