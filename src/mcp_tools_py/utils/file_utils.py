"""File operation utilities — thin re-export shim.

All functionality is provided by mcp_coder_utils.fs.
This module re-exports the public API for backward compatibility.
"""

from mcp_coder_utils.fs import read_file  # noqa: F401

__all__ = ["read_file"]
