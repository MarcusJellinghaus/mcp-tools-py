"""Functions for running tach architecture boundary checks."""

from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import execute_command


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
        Status line followed by tach output, or fallback message if no output.
    """
    command = [tach_binary, "check", "--output", "json"]

    result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return f"tach check timed out after {timeout_seconds} seconds."
    if result.execution_error:
        return f"tach check failed to run: {result.execution_error}"

    output = result.stdout
    if result.stderr:
        output = output + "\n" + result.stderr if output else result.stderr

    stripped = output.strip()
    if stripped:
        return f"tach check completed:\n{stripped}"
    return "tach check passed (no output)."
