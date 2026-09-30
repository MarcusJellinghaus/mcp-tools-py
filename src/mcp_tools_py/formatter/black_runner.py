"""Runner for black code formatter.

Invokes black as a subprocess and returns a FormatterResult.
"""

import time

from mcp_tools_py.formatter.common import (
    combine_output,
    formatter_binary,
    truncate_output,
    version_line,
)
from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import execute_command


def _parse_black_changed_files(output: str) -> list[str]:
    """Parse file paths from black output.

    Black reports changed files as:
    - Normal mode: ``reformatted src/foo.py``
    - Check mode: ``would reformat src/foo.py``

    Returns:
        Paths of files black reformatted (or would reformat).
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
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult:
    """Run black on target directories.

    Args:
        python_executable: Deprecated. Accepted and ignored; black runs from
            `environment`.
        target_dirs: List of directories to format.
        project_dir: Root project directory (cwd for subprocess).
        check_only: If True, pass --check to only verify formatting.
        timeout_seconds: Maximum seconds to wait for black.
        environment: Environment whose black console script runs. None means
            mcp-tools-py's own environment.

    Returns:
        FormatterResult with output, success status, and changed files.
    """
    env = environment or PythonEnvironment.resolve()
    binary = formatter_binary("black", env)
    if binary is None:
        return FormatterResult(
            output=f"black is not available: no console script found in {env.bin_dir}",
            success=False,
            files_changed=[],
        )

    command = [binary]
    if check_only:
        command.append("--check")
    command.extend(target_dirs)

    started = time.monotonic()
    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return FormatterResult(
            output=f"black timed out after {timeout_seconds} seconds.",
            success=False,
            files_changed=[],
        )

    if result.execution_error:
        return FormatterResult(
            output=f"black failed to run: {result.execution_error}",
            success=False,
            files_changed=[],
        )

    output = combine_output(result)
    remaining = int(timeout_seconds - (time.monotonic() - started))
    banner = version_line("black", binary, remaining)

    return FormatterResult(
        output=truncate_output(f"{banner}\n{output}"),
        success=result.return_code == 0,
        files_changed=_parse_black_changed_files(output),
    )
