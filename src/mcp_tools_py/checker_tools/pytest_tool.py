"""Pytest MCP tool registration."""

import logging
import os
from typing import TYPE_CHECKING, Dict, List, Optional

from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.utils import sanitize_extra_args
from mcp_tools_py.log_utils import log_function_call

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.server import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the pytest checker tool."""
    server = checker_tools._server

    @mcp.tool()
    @log_function_call
    def run_pytest_check(
        markers: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> str:
        """Run pytest on the project code and generate smart prompts for LLMs.

        Args:
            markers: Optional list of pytest markers to filter tests. Examples: ['slow', 'integration']
            extra_args: Optional list of additional pytest arguments for flexible test selection.
                       Examples: ['tests/test_file.py::test_function']
                       Use -v/-vv/-vvv in extra_args to control verbosity.
                       See "Flexible Test Selection" section below for common patterns.
            env_vars: Optional dictionary of environment variables for the subprocess.
            timeout_seconds: Maximum seconds to wait for the test run. Overrides the
                configured limit for this call. Must be a positive integer.
                Defaults to `[tool.mcp-tools-py]` config, then `--check-timeout`,
                then 300.

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
        if not server._is_tool_available("pytest"):
            return server.tool_unavailable_message("pytest")

        try:
            logger.info(
                "Starting pytest check",
                extra={
                    "project_dir": str(server.project_dir),
                    "test_folder": server.test_folder,
                    "markers": markers,
                    "extra_args": extra_args,
                },
            )

            # Sanitize extra_args: deduplicate flags, extract verbosity
            sanitized = sanitize_extra_args(
                extra_args, markers, project_dir=str(server.project_dir)
            )

            # Log any deduplication notes
            for note in sanitized.notes:
                logger.info("extra_args sanitized", extra={"note": note})

            # Run pytest
            test_results = check_code_with_pytest(
                project_dir=str(server.project_dir),
                test_folder=server.test_folder,
                python_executable=server._resolved_python,
                markers=markers,
                verbosity=sanitized.verbosity,
                extra_args=sanitized.cleaned_args,
                env_vars=env_vars,
                venv_bin=os.path.dirname(server._resolved_python),
                keep_temp_files=server.keep_temp_files,
                skip_default_test_folder=sanitized.has_path_args,
                timeout_seconds=server.resolve_timeout("pytest", timeout_seconds),
            )

            # Always show detailed failure output
            result = checker_tools._format_pytest_result_with_details(
                test_results, show_details=True
            )

            # Prepend deduplication notes so LLM can self-correct
            if sanitized.notes:
                notes_text = "\n".join(sanitized.notes)
                result = f"{notes_text}\n\n{result}"

            if test_results.get("success"):
                summary = test_results.get("summary", {})
                logger.info(
                    "Pytest execution completed",
                    extra={
                        "passed": summary.get("passed", 0) or 0,
                        "failed": summary.get("failed", 0) or 0,
                        "errors": summary.get("error", 0) or 0,
                        "duration": summary.get("duration", 0) or 0,
                    },
                )
            else:
                logger.error(
                    "Pytest execution failed",
                    extra={
                        "error": test_results.get("error", "Unknown error"),
                    },
                )

            return result

        except Exception as e:
            error_msg = f"Unexpected error running pytest: {type(e).__name__}: {e}"
            logger.error(
                "Pytest check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_dir": str(server.project_dir),
                },
            )
            return error_msg
