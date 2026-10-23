"""Model, JSON parser and runner for deptry dependency checks."""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import (
    check_tool_missing_error,
    execute_command,
    truncate_stderr,
)

logger = logging.getLogger(__name__)

_OUTPUT_FLAGS = ("--json-output", "-o")


class DeptryMessage(NamedTuple):
    """A single deptry finding."""

    code: str
    message: str
    module: str
    file: str
    line: int | None
    column: int | None


class DeptryResult(NamedTuple):
    """The complete deptry execution result."""

    return_code: int
    messages: list[DeptryMessage]
    error: str | None = None
    raw_output: str | None = None


def _require_str(value: Any) -> str:
    """Return ``value`` if it is a string.

    Raises:
        TypeError: If ``value`` is not a string.
    """
    if not isinstance(value, str):
        raise TypeError(f"expected a string, got {value!r}")
    return value


def _require_optional_int(value: Any) -> int | None:
    """Return ``value`` if it is an int or None.

    Raises:
        TypeError: If ``value`` is neither an int nor None.
    """
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise TypeError(f"expected an integer or null, got {value!r}")
    return value


def parse_deptry_json_output(content: str) -> tuple[list[DeptryMessage], str | None]:
    """Parse deptry's ``--json-output`` report.

    Args:
        content: The report file's content.

    Returns:
        ``(messages, None)`` on success, or ``([], error)`` when the content
        does not have the expected shape.
    """
    try:
        data = json.loads(content)
    except ValueError as exc:
        return [], f"Could not parse deptry JSON output: {exc!r}"
    if not isinstance(data, list):
        return [], (
            "Could not parse deptry JSON output: "
            f"expected a list, got {type(data).__name__}"
        )
    try:
        messages = [
            DeptryMessage(
                code=_require_str(item["error"]["code"]),
                message=_require_str(item["error"]["message"]),
                module=_require_str(item["module"]),
                file=_require_str(item["location"]["file"]),
                line=_require_optional_int(item["location"]["line"]),
                column=_require_optional_int(item["location"]["column"]),
            )
            for item in data
        ]
    except (KeyError, TypeError, ValueError) as exc:
        return [], f"Could not parse deptry JSON output: {exc!r}"
    return messages, None


def _rejected_flag(extra_args: list[str] | None) -> str | None:
    """Find an output flag in ``extra_args``.

    Returns:
        The first output flag, or None when there is none.
    """
    for arg in extra_args or []:
        if arg in _OUTPUT_FLAGS or arg.startswith("--json-output="):
            return arg
    return None


def _with_snippet(message: str, stderr: str) -> str:
    """Append a truncated stderr snippet to ``message``.

    Returns:
        ``message``, followed by the snippet when stderr is not empty.
    """
    stripped = stderr.strip()
    if not stripped:
        return message
    return f"{message}: {truncate_stderr(stripped)}"


@log_function_call
def run_deptry_check_impl(
    python_executable: str,
    project_dir: str,
    target_directories: list[str],
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> DeptryResult:
    """Run deptry in the project's environment and return a structured result.

    deptry writes its JSON report to a temp file via ``--json-output``. Only
    exit code 0 or 1 together with a report that exists and parses counts as
    a result; anything else is an error.

    Args:
        python_executable: Project interpreter that runs ``-m deptry``.
        project_dir: Directory to run deptry in.
        target_directories: Directories to analyze.
        extra_args: Additional deptry CLI flags.
        timeout_seconds: Maximum seconds to wait for deptry.

    Returns:
        DeptryResult with parsed messages, or an execution error.

    Raises:
        FileNotFoundError: If the project directory does not exist.
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    flag = _rejected_flag(extra_args)
    if flag is not None:
        return DeptryResult(
            return_code=-1,
            messages=[],
            error=(
                f"{flag} changes where deptry writes its report and is not "
                "supported; run_deptry_check reads the JSON report itself."
            ),
        )

    temp_dir = tempfile.mkdtemp(prefix="deptry_runner_")
    try:
        output_file = os.path.join(temp_dir, "deptry_result.json")
        cmd = [
            python_executable,
            "-m",
            "deptry",
            *target_directories,
            "--json-output",
            output_file,
            *(extra_args or []),
        ]
        result = execute_command(cmd, cwd=project_dir, timeout_seconds=timeout_seconds)
        stderr = result.stderr or ""
        return_code = result.return_code

        tool_error = check_tool_missing_error(stderr, "deptry", python_executable)
        if tool_error:
            return DeptryResult(return_code=return_code, messages=[], error=tool_error)

        # execute_command sets execution_error too, so check the timeout first
        if result.timed_out:
            return DeptryResult(
                return_code=-1,
                messages=[],
                error=f"timed out after {timeout_seconds} seconds",
            )

        if result.execution_error:
            return DeptryResult(
                return_code=-1,
                messages=[],
                error=_with_snippet(str(result.execution_error), stderr),
            )

        if return_code not in (0, 1):
            return DeptryResult(
                return_code=return_code,
                messages=[],
                error=_with_snippet(f"deptry exited with code {return_code}", stderr),
            )

        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            return DeptryResult(
                return_code=return_code,
                messages=[],
                error=_with_snippet(
                    f"deptry produced no JSON output file (exit code {return_code})",
                    stderr,
                ),
            )

        content = Path(output_file).read_text(encoding="utf-8")
        messages, parse_error = parse_deptry_json_output(content)
        if parse_error:
            return DeptryResult(
                return_code=return_code,
                messages=[],
                error=_with_snippet(parse_error, stderr),
            )

        return DeptryResult(
            return_code=return_code, messages=messages, raw_output=content
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
