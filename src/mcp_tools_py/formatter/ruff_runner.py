"""Runners for the ruff formatter steps.

Invokes ruff as a subprocess and returns a FormatterResult.
"""

import re
import time

from mcp_tools_py.formatter.common import (
    combine_output,
    formatter_binary,
    relative_path,
    truncate_output,
    version_line,
)
from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.ruff_parsing import RuffMessage, parse_ruff_json_output
from mcp_tools_py.utils.subprocess_runner import execute_command

# Anchored on `:<line>:<col>` so a drive-letter colon does not cut the path.
_FAILED_TO_PARSE = re.compile(r"error: Failed to parse (.+?):\d+:\d+")


def _is_syntax_error(m: RuffMessage) -> bool:
    """Whether a ruff diagnostic reports a file ruff could not parse.

    Returns:
        True for an ``invalid-syntax`` diagnostic, or one with no code.
    """
    return not m.code or m.code == "invalid-syntax"


def _render_diagnostics(messages: list[RuffMessage], project_dir: str) -> str:
    """One line per diagnostic: '<relative_path>: <code or invalid-syntax> <message>'.

    Returns:
        The rendered lines joined by newlines, or ``""`` when there are none.
    """
    return "\n".join(
        f"{relative_path(m.filename, project_dir)}: "
        f"{m.code or 'invalid-syntax'} {m.message}"
        for m in messages
    )


def _dedup(paths: list[str]) -> list[str]:
    """Paths in first-seen order, without duplicates.

    Returns:
        The deduplicated list.
    """
    return list(dict.fromkeys(paths))


def run_ruff_format(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult:
    """Run ``ruff format`` on target directories.

    Args:
        python_executable: Deprecated. Accepted and ignored; ruff runs from
            `environment`.
        target_dirs: List of directories to format.
        project_dir: Root project directory (cwd for subprocess).
        check_only: If True, pass ``--check --output-format json`` to only
            verify formatting.
        timeout_seconds: Maximum seconds to wait for ruff.
        environment: Environment whose ruff console script runs. None means
            mcp-tools-py's own environment.

    Returns:
        FormatterResult with project-relative, forward-slash paths.
        files_changed is empty in write mode, where ruff names no files.
        unparsable_files lists files ruff could not parse; ruff still formats
        the others.
    """
    env = environment or PythonEnvironment.resolve()
    binary = formatter_binary("ruff", env)
    if binary is None:
        return FormatterResult(
            output=f"ruff is not available: no console script found in {env.bin_dir}",
            success=False,
            files_changed=[],
        )

    command = [binary, "format"]
    if check_only:
        command.extend(["--check", "--output-format", "json"])
    command.extend(target_dirs)

    started = time.monotonic()
    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return FormatterResult(
            output=f"ruff format timed out after {timeout_seconds} seconds.",
            success=False,
            files_changed=[],
        )

    if result.execution_error:
        return FormatterResult(
            output=f"ruff format failed to run: {result.execution_error}",
            success=False,
            files_changed=[],
        )

    remaining = int(timeout_seconds - (time.monotonic() - started))
    banner = version_line("ruff", binary, remaining)
    stderr_bad: list[str] = _FAILED_TO_PARSE.findall(result.stderr)

    if check_only:
        messages, parse_error = parse_ruff_json_output(result.stdout, project_dir)
        if parse_error:
            body = "\n".join(part for part in (parse_error, result.stderr) if part)
            return FormatterResult(
                output=truncate_output(f"{banner}\n{body}"),
                success=False,
                files_changed=[],
            )
        changed = [m.filename for m in messages if m.code == "unformatted"]
        json_bad = [m.filename for m in messages if _is_syntax_error(m)]
        rendered = _render_diagnostics(messages, project_dir)
        combined = "\n".join(part for part in (rendered, result.stderr) if part)
    else:
        changed, json_bad = [], []
        combined = combine_output(result)

    return FormatterResult(
        output=truncate_output(f"{banner}\n{combined}"),
        success=result.return_code == 0,
        files_changed=_dedup([relative_path(p, project_dir) for p in changed]),
        unparsable_files=_dedup(
            [relative_path(p, project_dir) for p in stderr_bad + json_bad]
        ),
    )
