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
            venv_path: Optional path to a virtual environment to activate for running tests. When specified, the Python executable from this venv will be used instead of python_executable.
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
            FileNotFoundError: If `venv_path` is set but its python binary is missing.
        """
        if self.venv_path:
            if os.name == "nt":
                python = os.path.join(self.venv_path, "Scripts", "python.exe")
            else:
                python = os.path.join(self.venv_path, "bin", "python")
            if not os.path.exists(python):
                raise FileNotFoundError(
                    f"Python executable not found in virtual environment: {python}"
                )
            return python
        elif self.python_executable:
            return self.python_executable
        else:
            return sys.executable

    def _check_tool_availability(self) -> dict[str, bool]:
        """Check availability of file-existence tools (lint-imports, vulture, ruff, bandit).

        Returns:
            Mapping of tool name to availability flag.
        """
        availability: dict[str, bool] = {}

        # lint-imports: check via file existence (not subprocess)
        lint_imports_available = False
        binary: Optional[str] = None
        if self.venv_path:
            if os.name == "nt":
                binary = os.path.join(self.venv_path, "Scripts", "lint-imports.exe")
            else:
                binary = os.path.join(self.venv_path, "bin", "lint-imports")
            lint_imports_available = os.path.exists(binary)
        self._lint_imports_binary: Optional[str] = (
            binary if lint_imports_available else None
        )
        availability["lint-imports"] = lint_imports_available
        if not lint_imports_available:
            logger.warning(
                "lint-imports not found. Ensure --venv-path points to "
                "an environment where lint-imports is installed."
            )

        # vulture: check via file existence (not subprocess)
        vulture_available = False
        vulture_binary: Optional[str] = None
        if self.venv_path:
            if os.name == "nt":
                vulture_binary = os.path.join(self.venv_path, "Scripts", "vulture.exe")
            else:
                vulture_binary = os.path.join(self.venv_path, "bin", "vulture")
            vulture_available = os.path.exists(vulture_binary)
        self._vulture_binary: Optional[str] = (
            vulture_binary if vulture_available else None
        )
        availability["vulture"] = vulture_available
        if not vulture_available:
            logger.warning(
                "vulture not found. Ensure --venv-path points to "
                "an environment where vulture is installed."
            )

        # ruff: check via file existence (not subprocess)
        ruff_available = False
        ruff_binary: Optional[str] = None
        if self.venv_path:
            if os.name == "nt":
                ruff_binary = os.path.join(self.venv_path, "Scripts", "ruff.exe")
            else:
                ruff_binary = os.path.join(self.venv_path, "bin", "ruff")
            ruff_available = os.path.exists(ruff_binary)
        self._ruff_binary: Optional[str] = ruff_binary if ruff_available else None
        availability["ruff"] = ruff_available
        if not ruff_available:
            logger.warning(
                "ruff not found. Ensure --venv-path points to "
                "an environment where ruff is installed."
            )

        # bandit: check via file existence (not subprocess)
        bandit_available = False
        bandit_binary: Optional[str] = None
        if self.venv_path:
            if os.name == "nt":
                bandit_binary = os.path.join(self.venv_path, "Scripts", "bandit.exe")
            else:
                bandit_binary = os.path.join(self.venv_path, "bin", "bandit")
            bandit_available = os.path.exists(bandit_binary)
        self._bandit_binary: Optional[str] = bandit_binary if bandit_available else None
        availability["bandit"] = bandit_available
        if not bandit_available:
            logger.warning(
                "bandit not found. Ensure --venv-path points to "
                "an environment where bandit is installed."
            )

        # tach: check via file existence (not subprocess)
        tach_available = False
        tach_binary: Optional[str] = None
        if self.venv_path:
            if os.name == "nt":
                tach_binary = os.path.join(self.venv_path, "Scripts", "tach.exe")
            else:
                tach_binary = os.path.join(self.venv_path, "bin", "tach")
            tach_available = os.path.exists(tach_binary)
        self._tach_binary: Optional[str] = tach_binary if tach_available else None
        availability["tach"] = tach_available
        if not tach_available:
            logger.warning(
                "tach not found. Ensure --venv-path points to "
                "an environment where tach is installed."
            )

        return availability

    def _is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available, running subprocess check on first call.

        Returns:
            True if `python -m <tool_name> --version` succeeds.
        """
        if tool_name in self._tool_availability:
            return self._tool_availability[tool_name]
        result = execute_command(
            [self._resolved_python, "-m", tool_name, "--version"],
            timeout_seconds=10,
        )
        available = result.return_code == 0 and not result.execution_error
        if available:
            logger.info("%s version: %s", tool_name, result.stdout.strip())
        else:
            logger.warning(
                "%s not found in %s. "
                "Ensure --python-executable and --venv-path point to "
                "the environment where %s is installed.",
                tool_name,
                self._resolved_python,
                tool_name,
            )
        self._tool_availability[tool_name] = available
        return available

    def resolve_timeout(self, tool: ToolName, explicit: Optional[int] = None) -> int:
        """Resolve the subprocess timeout in seconds for one program.

        Args:
            tool: Name of the program the timeout applies to.
            explicit: Per-call timeout supplied by the caller, if any.

        Returns:
            Positive number of seconds.

        Raises:
            ValueError: If pyproject.toml is malformed or a configured value is invalid.
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
        venv_path: Optional path to a virtual environment to activate for running tests. When specified, the Python executable from this venv will be used instead of python_executable.
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
