"""Logging utilities — thin re-export shim.

All functionality is provided by mcp_coder_utils.log_utils.
This module re-exports the public API for backward compatibility.
"""

from mcp_coder_utils.log_utils import (  # noqa: F401
    OUTPUT,
    log_function_call,
    setup_logging,
)

__all__ = [
    "OUTPUT",
    "log_function_call",
    "setup_logging",
]
