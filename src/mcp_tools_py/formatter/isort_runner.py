"""Runner for isort import sorter.

Invokes isort as a subprocess and returns a FormatterResult.
"""

import re

from mcp_tools_py.formatter.common import formatter_binary
from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import execute_command

_MAX_LINES = 200
_UNPARSABLE_RE = re.compile(r"Unable to parse file (.+) due to ")


def _truncate_output(text: str) -> str:
    """Truncate output to a maximum number of lines.

    Returns:
        Original text, or text capped at `_MAX_LINES` with a marker.
    """
    lines = text.splitlines()
    if len(lines) <= _MAX_LINES:
        return text
    truncated = lines[:_MAX_LINES]
    remaining = len(lines) - _MAX_LINES
    truncated.append(f"... (truncated, {remaining} more lines)")
    return "\n".join(truncated)


def _parse_isort_changed_files(output: str) -> list[str]:
    """Parse file paths from isort output.

    isort reports changed files as:
    - Normal mode: ``Fixing src/foo.py``
    - Check mode: ``ERROR: src/foo.py Imports are incorrectly sorted ...``

    Returns:
        Paths of files isort sorted (or would sort).
    """
    files: list[str] = []
    for line in output.splitlines():
        if line.startswith("Fixing "):
            files.append(line[len("Fixing ") :])
        elif line.startswith("ERROR: ") and " Imports are incorrectly sorted" in line:
            path = line[len("ERROR: ") : line.index(" Imports are incorrectly sorted")]
            files.append(path)
    return files


def _parse_isort_unparsable_files(output: str) -> list[str]:
    """Parse file paths isort reported it could not read.

    isort warns ``Unable to parse file <path> due to <reason>`` and skips the
    file, while still exiting 0. The warning is prefixed by the warnings
    machinery, so the phrase is matched anywhere in the line.

    Returns:
        Paths of files isort skipped, in the order the warnings appeared.
    """
    return _UNPARSABLE_RE.findall(output)


def run_isort(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult:
    """Run isort on target directories.

    Args:
        python_executable: Deprecated. Accepted and ignored; isort runs from
            `environment`.
        target_dirs: List of directories to sort imports in.
        project_dir: Root project directory (cwd for subprocess).
        check_only: If True, pass --check-only to only verify sorting.
        timeout_seconds: Maximum seconds to wait for isort.
        environment: Environment whose isort console script runs. None means
            mcp-tools-py's own environment.

    Returns:
        FormatterResult with output, changed files, and any files isort could
        not read. success is True only when isort exited 0 and read every file.
    """
    env = environment or PythonEnvironment.resolve()
    binary = formatter_binary("isort", env)
    if binary is None:
        return FormatterResult(
            output=f"isort is not available: no console script found in {env.bin_dir}",
            success=False,
            files_changed=[],
        )

    command = [binary]
    if check_only:
        command.append("--check-only")
    command.extend(target_dirs)

    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return FormatterResult(
            output=f"isort timed out after {timeout_seconds} seconds.",
            success=False,
            files_changed=[],
        )

    if result.execution_error:
        return FormatterResult(
            output=f"isort failed to run: {result.execution_error}",
            success=False,
            files_changed=[],
        )

    output_parts: list[str] = []
    if result.stdout:
        output_parts.append(result.stdout)
    if result.stderr:
        output_parts.append(result.stderr)
    output = "\n".join(output_parts) if output_parts else ""

    unparsable_files = _parse_isort_unparsable_files(output)

    return FormatterResult(
        output=_truncate_output(output),
        success=result.return_code == 0 and not unparsable_files,
        files_changed=_parse_isort_changed_files(output),
        unparsable_files=unparsable_files,
    )
