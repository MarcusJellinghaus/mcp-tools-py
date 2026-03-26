"""Checker tools extracted from server.py for pylint, pytest, mypy, and lint-imports."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog

from mcp_tools_py.code_checker_mypy import get_mypy_prompt
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

if TYPE_CHECKING:
    from mcp_tools_py.server import CodeCheckerServer, FastMCPProtocol

logger = logging.getLogger(__name__)
structured_logger = structlog.get_logger(__name__)


class CheckerTools:
    """Registers pylint, pytest, mypy, and lint-imports checker tools on an MCP server."""

    def __init__(self, server: "CodeCheckerServer") -> None:
        self._server = server

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all checker tools with the MCP server."""
        self._register_pylint(mcp)
        self._register_pytest(mcp)
        self._register_mypy(mcp)
        self._register_lint_imports(mcp)

    def _register_pylint(self, mcp: "FastMCPProtocol") -> None:
        """Register the pylint checker tool."""

        @mcp.tool()
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
            if not self._server._tool_availability.get("pylint", False):
                return (
                    f"pylint is not available in the configured Python environment "
                    f"({self._server._resolved_python}). Ensure --python-executable and "
                    f"--venv-path point to the environment where pylint is installed. "
                    f"Restart the server after installing."
                )

            try:
                logger.info(
                    f"Running pylint check on project directory: {self._server.project_dir}"
                )
                structured_logger.info(
                    "Starting pylint check",
                    project_dir=str(self._server.project_dir),
                    extra_args=extra_args,
                    target_directories=target_directories,
                    max_issues=max_issues,
                )

                pylint_prompt = get_pylint_prompt(
                    str(self._server.project_dir),
                    python_executable=self._server._resolved_python,
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
                    project_dir=str(self._server.project_dir),
                )
                raise

    def _register_pytest(self, mcp: "FastMCPProtocol") -> None:
        """Register the pytest checker tool."""

        @mcp.tool()
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
            if not self._server._tool_availability.get("pytest", False):
                return (
                    f"pytest is not available in the configured Python environment "
                    f"({self._server._resolved_python}). Ensure --python-executable and "
                    f"--venv-path point to the environment where pytest is installed. "
                    f"Restart the server after installing."
                )

            try:
                logger.info(
                    f"Running pytest check on project directory: {self._server.project_dir}"
                )
                structured_logger.info(
                    "Starting pytest check",
                    project_dir=str(self._server.project_dir),
                    test_folder=self._server.test_folder,
                    markers=markers,
                    extra_args=extra_args,
                )

                # Sanitize extra_args: deduplicate flags, extract verbosity
                sanitized = sanitize_extra_args(
                    extra_args, markers, project_dir=str(self._server.project_dir)
                )

                # Always add -s for print statement capture
                final_extra_args = sanitized.cleaned_args + ["-s"]

                # Log any deduplication notes
                for note in sanitized.notes:
                    structured_logger.info("extra_args sanitized", note=note)

                # Run pytest
                test_results = check_code_with_pytest(
                    project_dir=str(self._server.project_dir),
                    test_folder=self._server.test_folder,
                    python_executable=self._server._resolved_python,
                    markers=markers,
                    verbosity=sanitized.verbosity,
                    extra_args=final_extra_args,
                    env_vars=env_vars,
                    venv_path=self._server.venv_path,
                    keep_temp_files=self._server.keep_temp_files,
                    skip_default_test_folder=sanitized.has_path_args,
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
                    project_dir=str(self._server.project_dir),
                )
                return error_msg

    def _register_mypy(self, mcp: "FastMCPProtocol") -> None:
        """Register the mypy checker tool."""

        @mcp.tool()
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
            if not self._server._tool_availability.get("mypy", False):
                return (
                    f"mypy is not available in the configured Python environment "
                    f"({self._server._resolved_python}). Ensure --python-executable and "
                    f"--venv-path point to the environment where mypy is installed. "
                    f"Restart the server after installing."
                )

            try:
                logger.info(
                    f"Running mypy check on project directory: {self._server.project_dir}"
                )
                structured_logger.info(
                    "Starting mypy check",
                    project_dir=str(self._server.project_dir),
                    strict=strict,
                    disable_error_codes=disable_error_codes,
                    target_directories=target_directories,
                )

                # Run mypy check
                mypy_prompt = get_mypy_prompt(
                    str(self._server.project_dir),
                    python_executable=self._server._resolved_python,
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
                    project_dir=str(self._server.project_dir),
                )
                raise

    def _register_lint_imports(self, mcp: "FastMCPProtocol") -> None:
        """Register the lint-imports checker tool."""

        @mcp.tool()
        @log_function_call
        def run_lint_imports_check(
            extra_args: Optional[List[str]] = None,
        ) -> str:
            """
            Run lint-imports on the project to check import contracts.

            Args:
                extra_args: Additional lint-imports arguments.
                    Examples: ["--contract", "layers"], ["--verbose"]

            Returns:
                Raw lint-imports output (stdout + stderr combined)
            """
            if not self._server._tool_availability.get("lint-imports", False):
                binary_path = self._server._lint_imports_binary or "N/A"
                return (
                    f"lint-imports is not available at {binary_path}. "
                    f"Ensure the virtual environment has import-linter installed "
                    f"and --venv-path is configured. Restart the server after installing."
                )

            try:
                logger.info(
                    f"Running lint-imports check on project directory: "
                    f"{self._server.project_dir}"
                )
                structured_logger.info(
                    "Starting lint-imports check",
                    project_dir=str(self._server.project_dir),
                    extra_args=extra_args,
                )

                binary = self._server._lint_imports_binary
                assert binary is not None  # guarded by availability check above
                command = [binary] + (extra_args or [])
                result = execute_command(command, cwd=str(self._server.project_dir))

                output = result.stdout
                if result.stderr:
                    output = output + "\n" + result.stderr if output else result.stderr

                structured_logger.info(
                    "lint-imports check completed",
                    return_code=result.return_code,
                    output_length=len(output),
                )

                return output.strip() or "lint-imports produced no output."

            except Exception as e:
                error_msg = (
                    f"Unexpected error running lint-imports: "
                    f"{type(e).__name__}: {e}"
                )
                logger.error(error_msg)
                structured_logger.error(
                    "lint-imports check failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    project_dir=str(self._server.project_dir),
                )
                return error_msg

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
