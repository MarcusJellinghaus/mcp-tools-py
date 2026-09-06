"""Library source inspection tools for MCP server."""

from typing import TYPE_CHECKING

from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.environment_info import probe_script_path
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import execute_command

if TYPE_CHECKING:
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol

# Timeout for one name resolution in the target environment.
SOURCE_TIMEOUT_SECONDS = 30

# How much of the child's stderr to quote back in a failure message.
_STDERR_SNIPPET = 500


def _get_library_source(import_path: str, max_lines: int, interpreter: str) -> str:
    """Retrieve source code for any importable Python symbol.

    The name is resolved by a child process running under `interpreter`, so
    that it resolves in the project's environment and nothing is imported
    into the server process.

    Args:
        import_path: Dotted import path (e.g. "os.path.join" or "json.JSONEncoder").
        max_lines: Maximum number of source lines to return. Must be >= 1.
        interpreter: Path to the Python interpreter to resolve the name in.

    Returns:
        Source code string, or an error message if resolution fails.
    """
    if max_lines < 1:
        return f"max_lines must be a positive integer (>= 1), got: {max_lines}"

    result = execute_command(
        [
            interpreter,
            str(probe_script_path()),
            "source",
            import_path,
            str(max_lines),
        ],
        timeout_seconds=SOURCE_TIMEOUT_SECONDS,
    )
    if result.timed_out:
        return (
            f"Error: resolving '{import_path}' timed out after "
            f"{SOURCE_TIMEOUT_SECONDS} seconds"
        )
    if result.execution_error:
        return f"Error: could not run {interpreter}: {result.execution_error}"
    if result.return_code != 0:
        detail = result.stderr.strip()[:_STDERR_SNIPPET]
        return (
            f"Error resolving '{import_path}' " f"(exit {result.return_code}): {detail}"
        )
    return result.stdout


class InspectTools:
    """Registers library inspection tools on an MCP server."""

    def __init__(self, environment: PythonEnvironment) -> None:
        """Store the environment that Python names resolve in.

        Args:
            environment: The project's Python environment.
        """
        self._environment = environment

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all inspection tools."""
        self._register_get_library_source(mcp)

    def _register_get_library_source(self, mcp: "FastMCPProtocol") -> None:
        """Register the get_library_source tool."""
        interpreter = str(self._environment.interpreter)

        @mcp.tool()
        @log_function_call
        def get_library_source(import_path: str, max_lines: int = 200) -> str:
            """Return the source code of any importable Python symbol.

            Resolves dotted import paths (e.g. "json.JSONEncoder",
            "os.path.join") in the project's configured Python environment
            and returns the source code. Useful for understanding library
            internals without leaving the editor.

            Args:
                import_path: Dotted Python import path to resolve.
                max_lines: Maximum source lines to return (default 200).
            """
            return _get_library_source(import_path, max_lines, interpreter)
