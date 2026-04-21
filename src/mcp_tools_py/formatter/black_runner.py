"""Runner for black code formatter.

Invokes black as a subprocess and returns a FormatterResult.
"""

from mcp_tools_py.utils.subprocess_runner import execute_command

from mcp_tools_py.formatter.models import FormatterResult

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


def _parse_black_changed_files(output: str) -> list[str]:
    """Parse file paths from black output.

    Black reports changed files as:
    - Normal mode: ``reformatted src/foo.py``
    - Check mode: ``would reformat src/foo.py``
    """
    files: list[str] = []
    for line in output.splitlines():
        if line.startswith("reformatted "):
            files.append(line[len("reformatted ") :])
        elif line.startswith("would reformat "):
            files.append(line[len("would reformat ") :])
    return files


def run_black(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
) -> FormatterResult:
    """Run black on target directories.

    Args:
        python_executable: Path to the Python executable.
        target_dirs: List of directories to format.
        project_dir: Root project directory (cwd for subprocess).
        check_only: If True, pass --check to only verify formatting.

    Returns:
        FormatterResult with output, success status, and changed files.
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

    return FormatterResult(
        output=_truncate_output(output),
        success=result.return_code == 0,
        files_changed=_parse_black_changed_files(output),
    )
