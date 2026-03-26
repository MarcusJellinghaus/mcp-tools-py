"""MCP server implementation for code checking functionality."""

import logging
import os
import sys
from pathlib import Path
from typing import Callable, Optional, Protocol, TypeVar

import structlog

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.inspect_library import InspectTools
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.refactoring import RefactoringTools
from mcp_tools_py.utility_tools import UtilityTools
from mcp_tools_py.utils.subprocess_runner import execute_command

# Type definitions for FastMCP
T = TypeVar("T")


class ToolDecorator(Protocol):
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]: ...


class FastMCPProtocol(Protocol):
    def tool(self) -> ToolDecorator: ...
    def run(self) -> None: ...


# Initialize loggers
logger = logging.getLogger(__name__)
structured_logger = structlog.get_logger(__name__)


class CodeCheckerServer:
    """MCP server for code checking functionality."""

    def __init__(
        self,
        project_dir: Path,
        python_executable: Optional[str] = None,
        venv_path: Optional[str] = None,
        test_folder: str = "tests",
        keep_temp_files: bool = False,
        refactoring_timeout: int = 120,
    ) -> None:
        """
        Initialize the server with the project directory and Python configuration.

        Args:
            project_dir: Path to the project directory to check
            python_executable: Optional path to Python interpreter to use for running tests. If None, defaults to sys.executable.
            venv_path: Optional path to a virtual environment to activate for running tests. When specified, the Python executable from this venv will be used instead of python_executable.
            test_folder: Path to the test folder (relative to project_dir). Defaults to 'tests'.
            keep_temp_files: Whether to keep temporary files after test execution. Useful for debugging when tests fail.
            refactoring_timeout: Timeout in seconds for rope refactoring operations.
        """
        self.project_dir = project_dir
        self.python_executable = python_executable
        self.venv_path = venv_path
        self.test_folder = test_folder
        self.keep_temp_files = keep_temp_files
        self.refactoring_timeout = refactoring_timeout

        # Import FastMCP
        from mcp.server.fastmcp import FastMCP

        self.mcp: FastMCPProtocol = FastMCP("Code Checker Service")
        self._resolved_python = self._resolve_python_executable()
        self._tool_availability = self._check_tool_availability()
        CheckerTools(self).register(self.mcp)
        RefactoringTools(self.project_dir, timeout=self.refactoring_timeout).register(
            self.mcp
        )
        UtilityTools().register(self.mcp)
        InspectTools().register(self.mcp)
        structured_logger.debug(
            "Tool environment resolved",
            python_executable=self._resolved_python,
            tool_availability=self._tool_availability,
        )

    def _resolve_python_executable(self) -> str:
        """Centralize venv -> python_executable -> sys.executable resolution."""
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
        """Check availability of pytest, pylint, mypy, and lint-imports."""
        availability: dict[str, bool] = {}
        for tool in ["pytest", "pylint", "mypy"]:
            result = execute_command(
                [self._resolved_python, "-m", tool, "--version"],
                timeout_seconds=10,
            )
            available = result.return_code == 0 and not result.execution_error
            availability[tool] = available
            if not available:
                logger.warning(
                    f"{tool} not found in {self._resolved_python}. "
                    f"Ensure --python-executable and --venv-path point to "
                    f"the environment where {tool} is installed."
                )

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

        return availability

    @log_function_call
    def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting MCP server")
        structured_logger.info("Starting MCP server")
        self.mcp.run()


@log_function_call
def create_server(
    project_dir: Path,
    python_executable: Optional[str] = None,
    venv_path: Optional[str] = None,
    test_folder: str = "tests",
    keep_temp_files: bool = False,
    refactoring_timeout: int = 120,
) -> CodeCheckerServer:
    """
    Create a new CodeCheckerServer instance.

    Args:
        project_dir: Path to the project directory to check
        python_executable: Optional path to Python interpreter to use for running tests. If None, defaults to sys.executable.
        venv_path: Optional path to a virtual environment to activate for running tests. When specified, the Python executable from this venv will be used instead of python_executable.
        test_folder: Path to the test folder (relative to project_dir). Defaults to 'tests'.
        keep_temp_files: Whether to keep temporary files after test execution. Useful for debugging when tests fail.
        refactoring_timeout: Timeout in seconds for rope refactoring operations.

    Returns:
        A new CodeCheckerServer instance
    """
    return CodeCheckerServer(
        project_dir,
        python_executable=python_executable,
        venv_path=venv_path,
        test_folder=test_folder,
        keep_temp_files=keep_temp_files,
        refactoring_timeout=refactoring_timeout,
    )
