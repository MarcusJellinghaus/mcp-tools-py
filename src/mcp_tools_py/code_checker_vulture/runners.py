"""Functions for running vulture dead-code analysis."""

import os
from typing import NamedTuple

from mcp_tools_py.code_checker_vulture.parsers import (
    VultureMessage,
    parse_vulture_output,
)
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import execute_command


class VultureResult(NamedTuple):
    """Outcome of a vulture run.

    `error` is set when vulture timed out or failed to run; `unparsed` holds
    output lines that are not findings (stderr, --make-whitelist output).
    """

    error: str | None
    messages: list[VultureMessage]
    unparsed: list[str]


def run_vulture_check(
    vulture_binary: str,
    project_dir: str,
    target_directories: list[str],
    min_confidence: int = 60,
    extra_args: list[str] | None = None,
    whitelist_path: str | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> VultureResult:
    """Run vulture on the specified project directory and parse its output.

    Args:
        vulture_binary: Path to the vulture binary.
        project_dir: The path to the project directory.
        target_directories: Directories to scan relative to project_dir.
        min_confidence: Minimum confidence for reporting (default: 60).
        extra_args: Additional vulture arguments.
        whitelist_path: Optional absolute path to a vulture whitelist file.
        timeout_seconds: Maximum seconds to wait for vulture.

    Returns:
        The parsed result of stdout + stderr, or one carrying `error`.
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

    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return VultureResult(
            f"vulture timed out after {timeout_seconds} seconds.", [], []
        )
    if result.execution_error:
        return VultureResult(f"vulture failed to run: {result.execution_error}", [], [])

    messages, unparsed = parse_vulture_output(f"{result.stdout}\n{result.stderr}")
    return VultureResult(error=None, messages=messages, unparsed=unparsed)
