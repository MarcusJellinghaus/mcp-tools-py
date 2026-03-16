"""
Utility functions for pylint code checking.
"""

import os


def normalize_path(path: str, base_dir: str) -> str:
    """
    Normalize a path relative to the base directory.

    Args:
        path: The path to normalize
        base_dir: The base directory to make the path relative to

    Returns:
        Normalized path
    """
    # Normalize both paths to use the platform-specific separator
    normalized_path = path.replace("\\", os.path.sep).replace("/", os.path.sep)
    normalized_base = base_dir.replace("\\", os.path.sep).replace("/", os.path.sep)

    # Make path relative to base_dir if it starts with base_dir
    if normalized_path.startswith(normalized_base):
        prefix = normalized_base
        if not prefix.endswith(os.path.sep):
            prefix += os.path.sep
        normalized_path = normalized_path.replace(prefix, "", 1)

    return normalized_path
