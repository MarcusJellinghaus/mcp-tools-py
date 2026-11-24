"""Per-user app-data directory — thin re-export shim.

All functionality is provided by mcp_coder_utils.user_app_data.
This module re-exports the public API so the rest of the package
never imports mcp_coder_utils directly.
"""

from mcp_coder_utils.user_app_data import get_user_app_data_dir  # noqa: F401

__all__ = ["get_user_app_data_dir"]
