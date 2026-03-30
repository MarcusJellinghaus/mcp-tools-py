"""Utils package for shared utilities.

This package provides common utilities used across the codebase:
- subprocess_runner: Command execution with MCP STDIO isolation
- file_utils: File operation utilities
- project_config: Target directory resolution from pyproject.toml
"""

# Import from file_utils module
from .file_utils import read_file

# Import from project_config module
from .project_config import TargetDirs, get_target_directories

# Import from subprocess_runner module
from .subprocess_runner import (
    CommandOptions,
    CommandResult,
    execute_command,
    execute_subprocess,
)

__all__ = [
    # Core subprocess functionality
    "CommandOptions",
    "CommandResult",
    "execute_command",
    "execute_subprocess",
    # File utilities
    "read_file",
    # Project config
    "TargetDirs",
    "get_target_directories",
]
