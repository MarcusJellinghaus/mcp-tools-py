"""Helpers shared by the formatter runners."""

import os
import re

from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import CommandResult, execute_command

MAX_LINES = 200
_VERSION_RE = re.compile(r"\d+(\.\d+)+")


def formatter_binary(
    name: str, environment: PythonEnvironment | None = None
) -> str | None:
    """Locate `name`'s console script, defaulting to mcp-tools-py's own environment.

    Args:
        name: Console script to look for, e.g. ``"black"``.
        environment: Environment to search. None means mcp-tools-py's own,
            resolved afresh on each call.

    Returns:
        Path to the console script, or None when it is not there.
    """
    env = environment or PythonEnvironment.resolve()
    binary = env.binary(name)
    return str(binary) if binary is not None else None


def truncate_output(text: str) -> str:
    """Truncate output to a maximum number of lines.

    Returns:
        Original text, or text capped at `MAX_LINES` with a marker.
    """
    lines = text.splitlines()
    if len(lines) <= MAX_LINES:
        return text
    truncated = lines[:MAX_LINES]
    remaining = len(lines) - MAX_LINES
    truncated.append(f"... (truncated, {remaining} more lines)")
    return "\n".join(truncated)


def combine_output(result: CommandResult) -> str:
    """Join a command's stdout and stderr into one block.

    Returns:
        The non-empty streams joined by a newline, or ``""`` when both are empty.
    """
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def relative_path(path: str, project_dir: str) -> str:
    """Project-relative path with forward slashes; already-relative paths pass through.

    Only an absolute path is relativized: `os.path.relpath` on a relative path
    would re-anchor it against the process's cwd, not `project_dir`.

    Returns:
        `path` relative to `project_dir` if absolute, with ``/`` separators.
    """
    if os.path.isabs(path):
        path = os.path.relpath(path, project_dir)
    return path.replace(os.sep, "/")


def formatter_version(binary: str, timeout_seconds: int) -> str:
    """Version reported by `binary --version`.

    Never raises: the version is informational and must not fail a step.

    Args:
        binary: Path of the formatter binary that just ran.
        timeout_seconds: Budget left in the step; under one second skips the call.

    Returns:
        The first dotted version number in stdout, or ``"unknown"`` when it
        cannot be determined.
    """
    if timeout_seconds < 1:
        return "unknown"
    result = execute_command([binary, "--version"], timeout_seconds=timeout_seconds)
    if result.timed_out or result.execution_error or result.return_code != 0:
        return "unknown"
    match = _VERSION_RE.search(result.stdout)
    return match.group(0) if match else "unknown"


def version_line(tool: str, binary: str, timeout_seconds: int) -> str:
    """One-line version banner to prepend to a FormatterResult.output.

    Returns:
        ``"<tool> <version>"``.
    """
    return f"{tool} {formatter_version(binary, timeout_seconds)}"
