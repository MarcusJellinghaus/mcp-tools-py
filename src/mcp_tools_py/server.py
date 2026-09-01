"""MCP server implementation for code checking and formatting tools."""

import logging
import os
import sys
from pathlib import Path
from typing import Callable, Optional, Protocol, TypeVar

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.formatter import FormatterTools
from mcp_tools_py.inspect_library import InspectTools
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.refactoring import RefactoringTools
from mcp_tools_py.utility_tools import UtilityTools
from mcp_tools_py.utils.project_config import ToolName, get_check_timeout
from mcp_tools_py.utils.subprocess_runner import execute_command

# Type definitions for FastMCP
T = TypeVar("T")


class ToolDecorator(Protocol):
    """Protocol for an MCP tool-registration decorator."""

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Register `func` as an MCP tool and return it."""
        ...


class FastMCPProtocol(Protocol):
    """Subset of FastMCP's surface used by ToolServer."""

    def tool(self) -> ToolDecorator:
        """Return a decorator that registers a tool."""
        ...

    def run(self) -> None:
        """Run the MCP server event loop."""
        ...


# Initialize logger
logger = logging.getLogger(__name__)

# Timeout for the `python -m <module> --version` availability probe.
PROBE_TIMEOUT_SECONDS = 30

# Tool key -> module for `python -m <module>`, or None when the tool is only
# ever run through its console script. The console script is named after the key.
_TOOL_MODULES: dict[str, Optional[str]] = {
    "pytest": "pytest",
    "pylint": "pylint",
    "mypy": "mypy",
    "black": "black",
    "isort": "isort",
    "lint-imports": None,
    "vulture": None,
    "ruff": None,
    "bandit": None,
    "tach": None,
}

# Tool key -> distribution to install, when it differs from the key.
_TOOL_PACKAGES: dict[str, str] = {"lint-imports": "import-linter"}


class ToolServer:
    """MCP server for code checking and formatting tools."""

    def __init__(
        self,
        project_dir: Path,
        python_executable: Optional[str] = None,
        venv_path: Optional[str] = None,
        test_folder: str = "tests",
        keep_temp_files: bool = False,
        refactoring_timeout: int = 120,
        vulture_whitelist: str = "vulture_whitelist.py",
        check_timeout: Optional[int] = None,
    ) -> None:
        """Initialize the server with the project directory and Python configuration.

        Args:
            project_dir: Path to the project directory to check
            python_executable: Optional path to Python interpreter to use for running tests. If None, defaults to sys.executable.
            venv_path: Deprecated, use python_executable instead. Optional path to a virtual environment. When specified, the Python executable from this venv is used instead of python_executable, which is now its only effect: it no longer locates the tools.
            test_folder: Path to the test folder (relative to project_dir). Defaults to 'tests'.
            keep_temp_files: Whether to keep temporary files after test execution. Useful for debugging when tests fail.
            refactoring_timeout: Timeout in seconds for rope refactoring operations.
            vulture_whitelist: Filename for vulture whitelist file. Defaults to 'vulture_whitelist.py'.
            check_timeout: Server-level timeout in seconds for checker and formatter subprocesses. If None, per-tool configuration or the built-in defaults apply.
        """
        self.project_dir = project_dir
        self.python_executable = python_executable
        self.venv_path = venv_path
        self.test_folder = test_folder
        self.keep_temp_files = keep_temp_files
        self.refactoring_timeout = refactoring_timeout
        self.vulture_whitelist = vulture_whitelist
        self.check_timeout = check_timeout

        # Import FastMCP
        from mcp.server.fastmcp import FastMCP

        self.mcp: FastMCPProtocol = FastMCP("MCP Tools Service")
        self._resolved_python = self._resolve_python_executable()
        self._tool_binaries: dict[str, str] = {}
        self._tool_availability = self._check_tool_availability()
        CheckerTools(self).register(self.mcp)
        FormatterTools(self).register(self.mcp)
        RefactoringTools(self.project_dir, timeout=self.refactoring_timeout).register(
            self.mcp
        )
        UtilityTools().register(self.mcp)
        InspectTools().register(self.mcp)

    def _resolve_python_executable(self) -> str:
        """Centralize venv -> python_executable -> sys.executable resolution.

        Returns:
            Path to the Python interpreter to use for tool subprocesses.

        Raises:
            FileNotFoundError: If the resolved interpreter does not exist.
        """
        if self.venv_path:
            if os.name == "nt":
                python = os.path.join(self.venv_path, "Scripts", "python.exe")
            else:
                python = os.path.join(self.venv_path, "bin", "python")
            source = "--venv-path"
        elif self.python_executable:
            python, source = self.python_executable, "--python-executable"
        else:
            python, source = sys.executable, "sys.executable"

        if not os.path.exists(python):
            raise FileNotFoundError(
                f"Python interpreter not found: {python} (from {source})"
            )
        return python

    def _check_tool_availability(self) -> dict[str, bool]:
        """Locate the console-script tools next to the resolved interpreter.

        Returns:
            Mapping of tool key to availability flag.
        """
        availability: dict[str, bool] = {}

        for key, module in _TOOL_MODULES.items():
            if module is not None:
                # Probe group: detected lazily, on first use.
                continue
            path = self._script_path(key)
            if path is not None:
                self._tool_binaries[key] = path
            else:
                logger.warning("%s", self.tool_unavailable_message(key))
            availability[key] = path is not None

        return availability

    def _script_path(self, key: str) -> Optional[str]:
        """Locate the console script for a tool next to the resolved interpreter.

        Args:
            key: Tool key, which is also the console-script filename.

        Returns:
            Path to the console script, or None when it is not there.
        """
        name = f"{key}.exe" if os.name == "nt" else key
        path = os.path.join(os.path.dirname(self._resolved_python), name)
        return path if os.path.exists(path) else None

    def _is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available, probing on first call.

        Checks, in order: the cache, a console script next to the resolved
        interpreter, then `python -m <module> --version`. A probe that times out
        is assumed available; a tool with no module never probes.

        Args:
            tool_name: Tool key to look up.

        Returns:
            True if the tool is available.
        """
        if tool_name in self._tool_availability:
            return self._tool_availability[tool_name]

        script = self._script_path(tool_name)
        module = _TOOL_MODULES.get(tool_name)
        if script is not None:
            available = True
            if module is None:
                self._tool_binaries[tool_name] = script
        elif module is None:
            # Console-script-only tool: file existence is the entire check.
            available = False
        else:
            result = execute_command(
                [self._resolved_python, "-m", module, "--version"],
                timeout_seconds=PROBE_TIMEOUT_SECONDS,
                env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
            )
            if result.timed_out:
                available = True
                logger.warning(
                    "%s version probe timed out after %s seconds using %s. "
                    "Assuming %s is available.",
                    tool_name,
                    PROBE_TIMEOUT_SECONDS,
                    self._resolved_python,
                    tool_name,
                )
            else:
                available = result.return_code == 0 and not result.execution_error
                if available:
                    logger.info("%s version: %s", tool_name, result.stdout.strip())

        if not available:
            logger.warning("%s", self.tool_unavailable_message(tool_name))
        self._tool_availability[tool_name] = available
        return available

    def tool_unavailable_message(self, key: str, package: Optional[str] = None) -> str:
        """Build the standard "tool not available" message for `key`.

        Args:
            key: Tool key as used in `_tool_availability`.
            package: Distribution name to tell the user to install. Defaults to
                `_TOOL_PACKAGES`, which maps a key to its distribution when the
                two differ (import-linter provides `lint-imports`).

        Returns:
            A message naming --python-executable and the location searched.
        """
        name = package or _TOOL_PACKAGES.get(key, key)
        if _TOOL_MODULES.get(key) is None:
            searched = os.path.dirname(self._resolved_python)
            return (
                f"{key} is not available. No {key} console script was found in "
                f"{searched}. Ensure --python-executable points to an environment "
                f"where {name} is installed. Restart the server after installing."
            )
        return (
            f"{key} is not available in the configured Python environment "
            f"({self._resolved_python}). Ensure --python-executable points to the "
            f"environment where {name} is installed. "
            f"Restart the server after installing."
        )

    def resolve_timeout(self, tool: ToolName, explicit: Optional[int] = None) -> int:
        """Resolve the subprocess timeout in seconds for one program.

        Args:
            tool: Name of the program the timeout applies to.
            explicit: Per-call timeout supplied by the caller, if any.

        Returns:
            Positive number of seconds.  A ``ValueError`` propagates when
            pyproject.toml is malformed or a configured value is invalid.
        """
        return get_check_timeout(
            str(self.project_dir), tool, explicit, self.check_timeout
        )

    @log_function_call
    def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting MCP server")
        self.mcp.run()


@log_function_call
def create_server(
    project_dir: Path,
    python_executable: Optional[str] = None,
    venv_path: Optional[str] = None,
    test_folder: str = "tests",
    keep_temp_files: bool = False,
    refactoring_timeout: int = 120,
    vulture_whitelist: str = "vulture_whitelist.py",
    check_timeout: Optional[int] = None,
) -> ToolServer:
    """Create a new ToolServer instance.

    Args:
        project_dir: Path to the project directory to check
        python_executable: Optional path to Python interpreter to use for running tests. If None, defaults to sys.executable.
        venv_path: Deprecated, use python_executable instead. Optional path to a virtual environment. When specified, the Python executable from this venv is used instead of python_executable, which is now its only effect: it no longer locates the tools.
        test_folder: Path to the test folder (relative to project_dir). Defaults to 'tests'.
        keep_temp_files: Whether to keep temporary files after test execution. Useful for debugging when tests fail.
        refactoring_timeout: Timeout in seconds for rope refactoring operations.
        vulture_whitelist: Filename for vulture whitelist file. Defaults to 'vulture_whitelist.py'.
        check_timeout: Server-level timeout in seconds for checker and formatter subprocesses. If None, per-tool configuration or the built-in defaults apply.

    Returns:
        A new ToolServer instance
    """
    return ToolServer(
        project_dir,
        python_executable=python_executable,
        venv_path=venv_path,
        test_folder=test_folder,
        keep_temp_files=keep_temp_files,
        refactoring_timeout=refactoring_timeout,
        vulture_whitelist=vulture_whitelist,
        check_timeout=check_timeout,
    )
