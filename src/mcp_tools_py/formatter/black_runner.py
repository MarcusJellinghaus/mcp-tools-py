"""Runner for black code formatter.

Invokes black as a subprocess and returns raw text output.
"""

from mcp_tools_py.utils.subprocess_runner import execute_command

_MAX_LINES = 200


def _truncate_output(text: str) -> str:
    """Truncate output to a maximum number of lines."""
    lines = text.splitlines()
    if len(lines) <= _MAX_LINES:
        return text
    truncated = lines[:_MAX_LINES]
    remaining = len(lines) - _MAX_LINES
    truncated.append(f"... (truncated, {remaining} more lines)")
    return "\n".join(truncated)


def run_black(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
) -> tuple[str, bool]:
    """Run black on target directories.

    Args:
        python_executable: Path to the Python executable.
        target_dirs: List of directories to format.
        project_dir: Root project directory (cwd for subprocess).
        check_only: If True, pass --check to only verify formatting.

    Returns:
        Tuple of (output_text, success).
        success is True when return_code == 0.
    """
    command = [python_executable, "-m", "black"]
    if check_only:
        command.append("--check")
    command.extend(target_dirs)

    result = execute_command(command, cwd=project_dir)

    output_parts: list[str] = []
    if result.stdout:
        output_parts.append(result.stdout)
    if result.stderr:
        output_parts.append(result.stderr)
    output = "\n".join(output_parts) if output_parts else ""

    return _truncate_output(output), result.return_code == 0
