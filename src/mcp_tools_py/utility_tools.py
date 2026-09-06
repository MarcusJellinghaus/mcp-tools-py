"""Utility tools for general-purpose MCP operations."""

import time
from typing import TYPE_CHECKING

from mcp_tools_py.log_utils import log_function_call

if TYPE_CHECKING:
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol


class UtilityTools:
    """Registers utility tools on an MCP server."""

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all utility tools with the MCP server."""

        @mcp.tool()
        @log_function_call
        def sleep(sleep_seconds: float = 5.0) -> str:
            """Pause execution for the specified number of seconds.

            Args:
                sleep_seconds: Duration to sleep in seconds (0-300, default: 5.0).

            Returns:
                Confirmation string, or an error message for out-of-range input.
            """
            if sleep_seconds < 0:
                return "Error: sleep_seconds must be >= 0."
            if sleep_seconds > 300:
                return "Error: sleep_seconds must be <= 300."
            time.sleep(sleep_seconds)
            return f"Slept for {sleep_seconds} seconds."
