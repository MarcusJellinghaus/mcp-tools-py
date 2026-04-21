"""Functions for running vulture dead-code analysis."""

import os

from mcp_tools_py.utils.subprocess_runner import execute_command


def run_vulture_check(
    vulture_binary: str,
    project_dir: str,
    target_directories: list[str],
    min_confidence: int = 60,
    extra_args: list[str] | None = None,
    whitelist_path: str | None = None,
) -> str:
    """Run vulture on the specified project directory and return raw output.

    Args:
        vulture_binary: Path to the vulture binary.
        project_dir: The path to the project directory.
        target_directories: Directories to scan relative to project_dir.
        min_confidence: Minimum confidence for reporting (default: 60).
        extra_args: Additional vulture arguments.
        whitelist_path: Optional absolute path to a vulture whitelist file.

    Returns:
        Raw vulture output string (stdout + stderr combined), or fallback message.
    """
    paths: list[str] = list(target_directories)
    if whitelist_path and os.path.exists(whitelist_path):
        paths.append(whitelist_path)

    command = (
        [vulture_binary]
        + paths
        + ["--min-confidence", str(min_confidence)]
        + (extra_args or [])
    )

    result = execute_command(command, cwd=project_dir)

    output = result.stdout
    if result.stderr:
        output = output + "\n" + result.stderr if output else result.stderr

    return output.strip() or "vulture produced no output."
