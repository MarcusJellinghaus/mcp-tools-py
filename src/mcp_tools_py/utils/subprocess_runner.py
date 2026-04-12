"""Subprocess execution utilities — thin re-export shim.

All functionality is provided by mcp_coder_utils.subprocess_runner.
This module re-exports the public API for backward compatibility.
"""

from mcp_coder_utils.subprocess_runner import (  # noqa: F401
    MAX_STDERR_IN_ERROR,
    CalledProcessError,
    CommandOptions,
    CommandResult,
    SubprocessError,
    TimeoutExpired,
    check_tool_missing_error,
    execute_command,
    execute_subprocess,
    format_command,
    launch_process,
    prepare_env,
    truncate_stderr,
)

__all__ = [
    "CalledProcessError",
    "CommandOptions",
    "CommandResult",
    "MAX_STDERR_IN_ERROR",
    "SubprocessError",
    "TimeoutExpired",
    "check_tool_missing_error",
    "execute_command",
    "execute_subprocess",
    "format_command",
    "launch_process",
    "prepare_env",
    "truncate_stderr",
]
