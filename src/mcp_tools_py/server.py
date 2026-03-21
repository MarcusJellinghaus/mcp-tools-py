"""MCP server implementation for code checking functionality."""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar

import structlog

# Import all code checking modules at the top
from mcp_tools_py.code_checker_mypy import MypyResult, get_mypy_prompt
from mcp_tools_py.code_checker_pylint import get_pylint_prompt
from mcp_tools_py.code_checker_pytest.reporting import (
    MAX_FAILURES,
    MAX_OUTPUT_LINES,
    SMALL_TEST_RUN_THRESHOLD,
    create_prompt_for_failed_tests,
    should_show_details,
)
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.utils import sanitize_extra_args
from mcp_tools_py.log_utils import log_function_call
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
    ) -> None:
        """
        Initialize the server with the project directory and Python configuration.

        Args:
            project_dir: Path to the project directory to check
            python_executable: Optional path to Python interpreter to use for running tests. If None, defaults to sys.executable.
            venv_path: Optional path to a virtual environment to activate for running tests. When specified, the Python executable from this venv will be used instead of python_executable.
            test_folder: Path to the test folder (relative to project_dir). Defaults to 'tests'.
            keep_temp_files: Whether to keep temporary files after test execution. Useful for debugging when tests fail.
        """
        self.project_dir = project_dir
        self.python_executable = python_executable
        self.venv_path = venv_path
        self.test_folder = test_folder
        self.keep_temp_files = keep_temp_files

        # Import FastMCP
        from mcp.server.fastmcp import FastMCP

        self.mcp: FastMCPProtocol = FastMCP("Code Checker Service")
        self._register_tools()
        self._resolved_python = self._resolve_python_executable()
        self._tool_availability = self._check_tool_availability()
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
        """Check availability of pytest, pylint, and mypy in the resolved Python environment."""
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
        return availability

    def _format_pylint_result(self, pylint_prompt: Optional[str]) -> str:
        """Format pylint check result."""
        if pylint_prompt is None:
            return "Pylint check completed. No issues found that require attention."
        return pylint_prompt

    def _format_pytest_result_with_details(
        self, test_results: dict[str, Any], show_details: bool
    ) -> str:
        """Enhanced formatting that respects show_details parameter."""
        if not test_results["success"]:
            return f"Error running pytest: {test_results.get('error', 'Unknown error')}"

        summary = test_results.get("summary", {})
        if not isinstance(summary, dict):
            return "Error: Invalid test summary format"

        # Handle None values properly
        failed_count = summary.get("failed") or 0
        error_count = summary.get("error") or 0
        passed_count = summary.get("passed") or 0
        collected = summary.get("collected") or 0

        # Determine if we have failures that need attention
        failures_exist = (failed_count > 0 or error_count > 0) and test_results.get(
            "test_results"
        )

        if failures_exist:
            should_show = should_show_details(test_results, show_details)

            if should_show:
                # Use enhanced create_prompt_for_failed_tests with new parameters
                failed_tests_prompt = create_prompt_for_failed_tests(
                    test_results["test_results"],
                    max_number_of_tests_reported=MAX_FAILURES,  # Use constant
                    include_print_output=True,
                    max_failures=MAX_FAILURES,
                    max_output_lines=MAX_OUTPUT_LINES,  # Use constant
                )
                return (
                    f"Pytest found issues that need attention:\n\n{failed_tests_prompt}"
                )
            else:
                # NOTE: This branch is currently dead code -- show_details is
                # always passed as True from run_pytest_check().  Retained for
                # possible future use.  The hint below references the removed
                # show_details parameter and would need updating if re-enabled.
                hint = (
                    " Try show_details=True for more information."
                    if collected <= SMALL_TEST_RUN_THRESHOLD
                    else ""
                )
                return f"Pytest completed with failures.{hint}"
        else:
            # Success case - use existing logic
            if test_results.get("summary_text"):
                return f"Pytest check completed. {test_results['summary_text']}"
            else:
                return f"Pytest check completed. All {passed_count} tests passed successfully."

    def _format_mypy_result(self, mypy_prompt: str | None) -> str:
        """Format mypy check result."""
        if mypy_prompt is None:
            return "Mypy check completed. No type errors found."
        return f"Mypy found type issues that need attention:\n\n{mypy_prompt}"

    def _register_tools(self) -> None:
        """Register all tools with the MCP server."""

        @self.mcp.tool()
        @log_function_call
        def run_pylint_check(
            extra_args: Optional[List[str]] = None,
            target_directories: Optional[List[str]] = None,
            max_issues: int = 1,
        ) -> str:
            """
            Run pylint on the project code and generate smart prompts for LLMs.

            Args:
                extra_args: Additional pylint arguments.
                target_directories: Directories to analyze relative to project_dir. Defaults to ["src"] and "tests" if it exists.
                max_issues: Number of issue types to show in detail (default: 1). Remaining issues shown as summary counts.
            """
            if not self._tool_availability.get("pylint", False):
                return (
                    f"pylint is not available in the configured Python environment "
                    f"({self._resolved_python}). Ensure --python-executable and "
                    f"--venv-path point to the environment where pylint is installed. "
                    f"Restart the server after installing."
                )

            try:
                logger.info(
                    f"Running pylint check on project directory: {self.project_dir}"
                )
                structured_logger.info(
                    "Starting pylint check",
                    project_dir=str(self.project_dir),
                    extra_args=extra_args,
                    target_directories=target_directories,
                    max_issues=max_issues,
                )

                pylint_prompt = get_pylint_prompt(
                    str(self.project_dir),
                    python_executable=self._resolved_python,
                    extra_args=extra_args,
                    target_directories=target_directories,
                    max_issues=max_issues,
                )

                result = self._format_pylint_result(pylint_prompt)

                structured_logger.info(
                    "Pylint check completed",
                    issues_found=pylint_prompt is not None,
                    result_length=len(result),
                )

                return result

            except Exception as e:
                logger.error(f"Error running pylint check: {str(e)}")
                structured_logger.error(
                    "Pylint check failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    project_dir=str(self.project_dir),
                )
                raise

        @self.mcp.tool()
        @log_function_call
        def run_pytest_check(
            markers: Optional[List[str]] = None,
            extra_args: Optional[List[str]] = None,
            env_vars: Optional[Dict[str, str]] = None,
        ) -> str:
            """
            Run pytest on the project code and generate smart prompts for LLMs.

            Args:
                markers: Optional list of pytest markers to filter tests. Examples: ['slow', 'integration']
                extra_args: Optional list of additional pytest arguments for flexible test selection.
                           Examples: ['tests/test_file.py::test_function']
                           Use -v/-vv/-vvv in extra_args to control verbosity.
                           See "Flexible Test Selection" section below for common patterns.
                env_vars: Optional dictionary of environment variables for the subprocess.

            Returns:
                A string containing either pytest results or a prompt for an LLM to interpret

            Flexible Test Selection:
                Use extra_args to run specific tests or control pytest behavior:

                # Specific tests
                extra_args=["tests/test_math.py::test_addition"]
                extra_args=["tests/test_auth.py"]  # Entire file
                extra_args=["-k", "calculation"]  # Pattern matching

                # Output control
                extra_args=["-s"]  # Show print statements
                extra_args=["--tb=short"]  # Short tracebacks
                extra_args=["-vvv"]  # Maximum verbosity

                # Execution control
                extra_args=["-x"]  # Stop on first failure

            Examples:
                # Standard CI run
                run_pytest_check()

                # Debug specific test with verbose output
                run_pytest_check(
                    extra_args=["tests/test_math.py::test_calculation", "-vvv"]
                )

                # Integration test run
                run_pytest_check(markers=["integration"])
            """
            if not self._tool_availability.get("pytest", False):
                return (
                    f"pytest is not available in the configured Python environment "
                    f"({self._resolved_python}). Ensure --python-executable and "
                    f"--venv-path point to the environment where pytest is installed. "
                    f"Restart the server after installing."
                )

            try:
                logger.info(
                    f"Running pytest check on project directory: {self.project_dir}"
                )
                structured_logger.info(
                    "Starting pytest check",
                    project_dir=str(self.project_dir),
                    test_folder=self.test_folder,
                    markers=markers,
                    extra_args=extra_args,
                )

                # Sanitize extra_args: deduplicate flags, extract verbosity
                sanitized = sanitize_extra_args(extra_args, markers)

                # Always add -s for print statement capture
                final_extra_args = sanitized.cleaned_args + ["-s"]

                # Log any deduplication notes
                for note in sanitized.notes:
                    structured_logger.info("extra_args sanitized", note=note)

                # Run pytest
                test_results = check_code_with_pytest(
                    project_dir=str(self.project_dir),
                    test_folder=self.test_folder,
                    python_executable=self._resolved_python,
                    markers=markers,
                    verbosity=sanitized.verbosity,
                    extra_args=final_extra_args,
                    env_vars=env_vars,
                    venv_path=self.venv_path,
                    keep_temp_files=self.keep_temp_files,
                )

                # Always show detailed failure output
                result = self._format_pytest_result_with_details(
                    test_results, show_details=True
                )

                # Prepend deduplication notes so LLM can self-correct
                if sanitized.notes:
                    notes_text = "\n".join(sanitized.notes)
                    result = f"{notes_text}\n\n{result}"

                if test_results.get("success"):
                    summary = test_results.get("summary", {})
                    structured_logger.info(
                        "Pytest execution completed",
                        passed=summary.get("passed", 0) or 0,
                        failed=summary.get("failed", 0) or 0,
                        errors=summary.get("error", 0) or 0,
                        duration=summary.get("duration", 0) or 0,
                    )
                else:
                    structured_logger.error(
                        "Pytest execution failed",
                        error=test_results.get("error", "Unknown error"),
                    )

                return result

            except Exception as e:
                error_msg = f"Unexpected error running pytest: {type(e).__name__}: {e}"
                logger.error(error_msg)
                structured_logger.error(
                    "Pytest check failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    project_dir=str(self.project_dir),
                )
                return error_msg

        @self.mcp.tool()
        @log_function_call
        def run_mypy_check(
            strict: bool = True,
            disable_error_codes: list[str] | None = None,
            target_directories: list[str] | None = None,
            follow_imports: str | None = None,
            cache_dir: str | None = None,
        ) -> str:
            """
            Run mypy type checking on the project code.

            Args:
                strict: Use strict mode settings (default: True).
                    When True, applies comprehensive type checking with flags like
                    --strict, --warn-redundant-casts, --warn-unused-ignores, etc.
                disable_error_codes: Optional list of mypy error codes to ignore.
                    Common codes to disable:
                    - 'import': Import-related errors
                    - 'arg-type': Argument type mismatches
                    - 'no-untyped-def': Missing type annotations
                    - 'attr-defined': Attribute not defined errors
                    - 'var-annotated': Missing variable annotations
                target_directories: Optional list of directories to check relative to project_dir.
                    Defaults to ["src"] and conditionally "tests" if it exists.
                    Examples:
                    - ["src"] - Check only source code
                    - ["src", "tests"] - Check both source and tests
                    - ["mypackage"] - Check custom package
                    - ["."] - Check entire project
                follow_imports: How to handle imports during type checking.
                    Options:
                    - 'normal' (default): Follow and type check imported modules
                    - 'silent': Follow imports but suppress errors in imported modules
                    - 'skip': Don't follow imports, only check specified files
                    - 'error': Error if imports cannot be followed
                cache_dir: Optional custom cache directory for incremental checking.
                    Mypy uses caching to speed up subsequent runs.
                    Defaults to .mypy_cache in the project directory.

            Returns:
                A string containing mypy results or a prompt for an LLM to interpret
            """
            if not self._tool_availability.get("mypy", False):
                return (
                    f"mypy is not available in the configured Python environment "
                    f"({self._resolved_python}). Ensure --python-executable and "
                    f"--venv-path point to the environment where mypy is installed. "
                    f"Restart the server after installing."
                )

            try:
                logger.info(
                    f"Running mypy check on project directory: {self.project_dir}"
                )
                structured_logger.info(
                    "Starting mypy check",
                    project_dir=str(self.project_dir),
                    strict=strict,
                    disable_error_codes=disable_error_codes,
                    target_directories=target_directories,
                )

                # Run mypy check
                mypy_prompt = get_mypy_prompt(
                    str(self.project_dir),
                    python_executable=self._resolved_python,
                    strict=strict,
                    disable_error_codes=disable_error_codes,
                    target_directories=target_directories,
                    follow_imports=follow_imports,
                    cache_dir=cache_dir,
                )

                # Format result
                result = self._format_mypy_result(mypy_prompt)

                structured_logger.info(
                    "Mypy check completed",
                    issues_found=mypy_prompt is not None,
                    result_length=len(result),
                )

                return result

            except Exception as e:
                logger.error(f"Error running mypy check: {str(e)}")
                structured_logger.error(
                    "Mypy check failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    project_dir=str(self.project_dir),
                )
                raise

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
) -> CodeCheckerServer:
    """
    Create a new CodeCheckerServer instance.

    Args:
        project_dir: Path to the project directory to check
        python_executable: Optional path to Python interpreter to use for running tests. If None, defaults to sys.executable.
        venv_path: Optional path to a virtual environment to activate for running tests. When specified, the Python executable from this venv will be used instead of python_executable.
        test_folder: Path to the test folder (relative to project_dir). Defaults to 'tests'.
        keep_temp_files: Whether to keep temporary files after test execution. Useful for debugging when tests fail.

    Returns:
        A new CodeCheckerServer instance
    """
    return CodeCheckerServer(
        project_dir,
        python_executable=python_executable,
        venv_path=venv_path,
        test_folder=test_folder,
        keep_temp_files=keep_temp_files,
    )
