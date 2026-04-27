"""Functions for running tach architecture boundary checks."""

from mcp_tools_py.utils.subprocess_runner import execute_command


def run_tach_check(tach_binary: str, project_dir: str) -> str:
    """Run `tach check --output json` and return status line + raw output.

    Args:
        tach_binary: Path to the tach binary.
        project_dir: The path to the project directory.

    Returns:
        Status line followed by tach output, or fallback message if no output.
    """
    command = [tach_binary, "check", "--output", "json"]

    result = execute_command(command, cwd=project_dir)

    output = result.stdout
    if result.stderr:
        output = output + "\n" + result.stderr if output else result.stderr

    stripped = output.strip()
    if stripped:
        return f"tach check completed:\n{stripped}"
    return "tach check passed (no output)."
