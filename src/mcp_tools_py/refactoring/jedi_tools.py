"""Jedi-based symbol discovery and reference finding."""

from pathlib import Path


def list_symbols(project_dir: Path, file_path: str) -> str:
    """List all top-level symbols in a file.

    Args:
        project_dir: Absolute path to project root.
        file_path: File path relative to project root.

    Returns:
        Formatted string listing symbols, or error message.
    """
    raise NotImplementedError("Will be implemented in Step 3 Part B")


def find_references(project_dir: Path, file_path: str, symbol_name: str) -> str:
    """Find all references to a symbol across the project.

    Args:
        project_dir: Absolute path to project root.
        file_path: File path relative to project root.
        symbol_name: Name of the top-level symbol.

    Returns:
        Formatted string listing references, or error message.
    """
    raise NotImplementedError("Will be implemented in Step 3 Part B")
