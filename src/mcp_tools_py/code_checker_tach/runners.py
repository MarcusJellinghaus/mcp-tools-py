"""Functions for running tach architecture boundary checks."""

from typing import NamedTuple

from mcp_tools_py.code_checker_tach.parsers import TachDiagnostic, parse_tach_json
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import execute_command


class TachResult(NamedTuple):
    """Outcome of a `tach check` run.

    `error` is set when tach timed out or failed to run; `raw` holds the
    combined output when it could not be parsed.
    """

    error: str | None
    return_code: int
    diagnostics: list[TachDiagnostic]
    raw: str | None


def run_tach_check(
    tach_binary: str,
    project_dir: str,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> TachResult:
    """Run `tach check --output json` and parse its diagnostics.

    Args:
        tach_binary: Path to the tach binary.
        project_dir: The path to the project directory.
        timeout_seconds: Maximum seconds to wait for tach.

    Returns:
        The parsed result, one carrying `raw` when the output is not tach's
        JSON, or one carrying `error`.
    """
    command = [tach_binary, "check", "--output", "json"]

    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return TachResult(
            f"tach check timed out after {timeout_seconds} seconds.",
            result.return_code,
            [],
            None,
        )
    if result.execution_error:
        return TachResult(
            f"tach check failed to run: {result.execution_error}",
            result.return_code,
            [],
            None,
        )

    combined = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )
    if not combined:
        return TachResult(None, result.return_code, [], None)
    diagnostics = parse_tach_json(result.stdout) if result.stdout.strip() else None
    if diagnostics is None:
        return TachResult(None, result.return_code, [], combined)
    return TachResult(None, result.return_code, diagnostics, None)
