"""Functions for running tach architecture boundary checks."""

from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import CommandResult, execute_command


def format_tach_result(result: CommandResult) -> str:
    """Format a finished `tach check` run.

    Args:
        result: The completed tach command result.

    Returns:
        A status line from tach's exit code, followed by its combined stdout
        and stderr when there is any.
    """
    output = result.stdout
    if result.stderr:
        output = output + "\n" + result.stderr if output else result.stderr

    stripped = output.strip()
    if result.return_code == 0:
        if stripped:
            return f"tach check passed:\n{stripped}"
        return "tach check passed (no output)."
    if stripped:
        return f"tach check failed:\n{stripped}"
    return f"tach check failed (exit code {result.return_code}, no output)."


def run_tach_check(
    tach_binary: str,
    project_dir: str,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:
    """Run `tach check --output json` and return status line + raw output.

    Args:
        tach_binary: Path to the tach binary.
        project_dir: The path to the project directory.
        timeout_seconds: Maximum seconds to wait for tach.

    Returns:
        The text from `format_tach_result`, or a message when tach timed out
        or failed to run.
    """
    command = [tach_binary, "check", "--output", "json"]

    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return f"tach check timed out after {timeout_seconds} seconds."
    if result.execution_error:
        return f"tach check failed to run: {result.execution_error}"

    return format_tach_result(result)
