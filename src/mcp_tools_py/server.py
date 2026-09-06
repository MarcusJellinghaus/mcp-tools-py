"""MCP server implementation for code checking and formatting tools."""

import logging
from pathlib import Path
from typing import Callable, Optional, Protocol, TypeVar

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.formatter import FormatterTools
from mcp_tools_py.inspect_library import InspectTools
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.refactoring import RefactoringTools
from mcp_tools_py.utility_tools import UtilityTools
from mcp_tools_py.utils.environment_info import (
    TOOL_MODULES,
    TOOL_PACKAGES,
    EnvironmentInfo,
    get_environment_info,
)
from mcp_tools_py.utils.project_config import ToolName, get_check_timeout
from mcp_tools_py.utils.python_environment import PythonEnvironment

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
            python_executable: Optional path to the Python interpreter of the project's environment. The checkers run in it and library/symbol lookups resolve against it, so it must be the environment holding the project's dependencies and the checker tools. If None, defaults to sys.executable.
            venv_path: Deprecated, use python_executable instead. Optional path to a virtual environment. When specified, the Python executable from this venv is used instead of python_executable, which is now its only effect: it no longer locates the tools.
            test_folder: Path to the test folder (relative to project_dir). Defaults to 'tests'.
            keep_temp_files: Whether to keep temporary files after test execution. Useful for debugging when tests fail.
            refactoring_timeout: Timeout in seconds for rope refactoring operations.
            vulture_whitelist: Filename for vulture whitelist file. Defaults to 'vulture_whitelist.py'.
            check_timeout: Server-level timeout in seconds for checker and formatter subprocesses. If None, per-tool configuration or the built-in defaults apply.
        """
        self.project_dir = project_dir
        self.test_folder = test_folder
        self.keep_temp_files = keep_temp_files
        self.refactoring_timeout = refactoring_timeout
        self.vulture_whitelist = vulture_whitelist
        self.check_timeout = check_timeout

        # Import FastMCP
        from mcp.server.fastmcp import FastMCP

        self.mcp: FastMCPProtocol = FastMCP("MCP Tools Service")
        self.environment = PythonEnvironment.resolve(python_executable, venv_path)
        self._resolved_python = str(self.environment.interpreter)
        self._tool_binaries: dict[str, str] = {}
        self._tool_availability = self._check_tool_availability()
        CheckerTools(self).register(self.mcp)
        FormatterTools(self).register(self.mcp)
        RefactoringTools(
            self.project_dir, self.environment, timeout=self.refactoring_timeout
        ).register(self.mcp)
        UtilityTools().register(self.mcp)
        InspectTools(self.environment).register(self.mcp)

    def _check_tool_availability(self) -> dict[str, bool]:
        """Locate the console-script tools next to the resolved interpreter.

        Returns:
            Mapping of tool key to availability flag.
        """
        availability: dict[str, bool] = {}

        for key, module in TOOL_MODULES.items():
            if module is not None:
                # Probe group: detected lazily, on first use.
                continue
            path = self.environment.binary(key)
            if path is not None:
                self._tool_binaries[key] = str(path)
            else:
                logger.warning("%s", self.tool_unavailable_message(key))
            availability[key] = path is not None

        return availability

    def _is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available, probing the environment on first call.

        A console-script-only tool is answered from the filesystem; the probe
        cannot answer for one, because it is asked about module names. Every
        other tool is answered from the one-shot environment probe, which
        fails open: a probe that could not be trusted reports the tool
        available so the call proceeds and surfaces the real error.

        Args:
            tool_name: Tool key to look up.

        Returns:
            True if the tool is available.
        """
        if tool_name in self._tool_availability:
            return self._tool_availability[tool_name]

        if TOOL_MODULES.get(tool_name) is None:
            # Console-script-only tool: file existence is the entire check.
            available = self.environment.binary(tool_name) is not None
            if not available:
                logger.warning("%s", self.tool_unavailable_message(tool_name))
        else:
            info = get_environment_info(self._resolved_python)
            available = info.importable.get(tool_name, False)
            if info.error or not available:
                logger.warning("%s", self._probe_diagnosis(tool_name, info))

        self._tool_availability[tool_name] = available
        return available

    def _probe_diagnosis(self, tool_name: str, info: EnvironmentInfo) -> str:
        """Explain what the environment probe says about `tool_name`.

        Args:
            tool_name: Tool key that was looked up.
            info: What the probe reported about the resolved interpreter.

        Returns:
            One line naming the interpreter and, when the probe succeeded, the
            installed distribution of the same name if there is one — which
            turns a flag problem into a broken-install diagnosis.
        """
        if info.error:
            return (
                f"cannot describe the environment at {self._resolved_python}: "
                f"{info.error}. Assuming {tool_name} is available."
            )
        name = TOOL_PACKAGES.get(tool_name, tool_name)
        version = info.distributions.get(name.lower())
        if version is not None:
            return (
                f"{tool_name} is not importable by {self._resolved_python} "
                f"(Python {info.version}), though distribution {name} {version} "
                f"is installed"
            )
        return (
            f"{tool_name} is not installed in {self._resolved_python} "
            f"(Python {info.version}). Ensure --python-executable points at "
            f"the project's environment."
        )

    def tool_unavailable_message(self, key: str) -> str:
        """Build the standard "tool not available" message for `key`.

        Args:
            key: Tool key as used in `_tool_availability`.

        Returns:
            A message naming --python-executable and the location searched.
            The distribution to install comes from `TOOL_PACKAGES`, which maps
            a key to its distribution when the two differ (import-linter
            provides `lint-imports`).
        """
        name = TOOL_PACKAGES.get(key, key)
        if TOOL_MODULES.get(key) is None:
            searched = str(self.environment.bin_dir)
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
        python_executable: Optional path to the Python interpreter of the project's environment. The checkers run in it and library/symbol lookups resolve against it, so it must be the environment holding the project's dependencies and the checker tools. If None, defaults to sys.executable.
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
