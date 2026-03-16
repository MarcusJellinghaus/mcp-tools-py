"""
Utils package for shared utilities.

This package provides common utilities used across the codebase:
- subprocess_runner: Command execution with MCP STDIO isolation
- file_utils: File operation utilities
"""

# Import from file_utils module
from .file_utils import read_file

# Import from subprocess_runner module
from .subprocess_runner import (
    MAX_STDERR_IN_ERROR,
    CommandOptions,
    CommandResult,
    check_tool_missing_error,
    execute_command,
    execute_subprocess,
    get_python_isolation_env,
    is_python_command,
    truncate_stderr,
)

__all__ = [
    # Core subprocess functionality
    "CommandOptions",
    "CommandResult",
    "execute_command",
    "execute_subprocess",
    # Error transparency helpers
    "MAX_STDERR_IN_ERROR",
    "check_tool_missing_error",
    "truncate_stderr",
    # Environment and utility functions
    "get_python_isolation_env",
    "is_python_command",
    # File utilities
    "read_file",
]
