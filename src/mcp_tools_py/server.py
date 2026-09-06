"""MCP server implementation for code checking and formatting tools."""

import logging
from pathlib import Path
from typing import Optional

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.formatter import FormatterTools
from mcp_tools_py.inspect_library import InspectTools
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.refactoring import RefactoringTools
from mcp_tools_py.utility_tools import UtilityTools
from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.tool_context import CONSOLE_SCRIPT_TOOLS, ToolContext

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
        self.context = ToolContext(
            project_dir=self.project_dir,
            environment=self.environment,
            test_folder=self.test_folder,
            keep_temp_files=self.keep_temp_files,
            vulture_whitelist=self.vulture_whitelist,
            check_timeout=self.check_timeout,
        )
        self._warn_missing_console_scripts()
        CheckerTools(self.context).register(self.mcp)
        FormatterTools(self.context).register(self.mcp)
        RefactoringTools(
            self.project_dir, self.environment, timeout=self.refactoring_timeout
        ).register(self.mcp)
        UtilityTools().register(self.mcp)
        InspectTools(self.environment).register(self.mcp)

    def _warn_missing_console_scripts(self) -> None:
        """Warn at startup about console scripts missing next to the interpreter.

        Stores nothing: availability is answered at use time by the context.
        The five `python -m` tools are left to the lazy probe.
        """
        for key in sorted(CONSOLE_SCRIPT_TOOLS):
            if self.environment.binary(key) is None:
                logger.warning("%s", self.context.unavailable_message(key))

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
