"""Pytest MCP tool registration."""

import logging
import shutil
import tempfile
from typing import TYPE_CHECKING, Dict, List, Optional

from mcp_tools_py.code_checker_pytest.coverage import (
    coverage_args,
    format_coverage_digest,
    read_coverage_report,
    read_fail_under,
    selection_line,
)
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.utils import sanitize_extra_args
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.environment_info import get_environment_info
from mcp_tools_py.utils.project_config import (
    get_pytest_addopts,
    resolve_coverage_source,
)

if TYPE_CHECKING:
    from mcp_tools_py.checker_tools import CheckerTools
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol

logger = logging.getLogger(__name__)


def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    """Register the pytest checker tool."""
    context = checker_tools.context

    @mcp.tool()
    @log_function_call
    def run_pytest_check(
        markers: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[int] = None,
        coverage: bool = False,
        coverage_source: Optional[List[str]] = None,
        max_modules: int = 10,
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
            coverage: Measure coverage with pytest-cov (must be installed in the
                project's environment) and append a digest to the reply: total,
                modules ranked by missing statements with per-function line
                ranges, modules with nothing covered, and the test selection
                the numbers come from. The project's `fail_under` is not
                applied. Exclude code with coverage's own `omit` setting or
                `# pragma: no cover`.
            coverage_source: Directories to measure. Defaults to the project's
                source directories from pyproject.toml, excluding test paths.
            max_modules: How many modules the coverage digest details in each
                list (default: 10).

        Returns:
            A string containing either pytest results or a prompt for an LLM to interpret

        Flexible Test Selection:
            Use extra_args to run specific tests or control pytest behavior:

            # Specific tests
            extra_args=["tests/test_math.py::test_addition"]
            extra_args=["tests/test_auth.py"]  # Entire file
            extra_args=["-k", "calculation"]  # Pattern matching

            # Output control
            extra_args=["-s"]  # Show captured print output of passing tests
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

            # Coverage digest for the full suite
            run_pytest_check(coverage=True)
        """
        if not context.is_tool_available("pytest"):
            return context.unavailable_message("pytest")

        project_dir = str(context.project_dir)
        interpreter = str(context.environment.interpreter)
        temp_dir: Optional[str] = None
        try:
            sources: List[str] = []
            if coverage:
                info = get_environment_info(interpreter)
                if not info.error and "pytest-cov" not in info.distributions:
                    return context.unavailable_message("pytest-cov")
                resolved = resolve_coverage_source(project_dir, coverage_source)
                if isinstance(resolved, str):
                    return resolved
                sources = resolved

            logger.info(
                "Starting pytest check",
                extra={
                    "project_dir": str(context.project_dir),
                    "test_folder": context.test_folder,
                    "markers": markers,
                    "extra_args": extra_args,
                },
            )

            # Sanitize extra_args: deduplicate flags, extract verbosity
            sanitized = sanitize_extra_args(
                extra_args, markers, project_dir=project_dir
            )

            # Log any deduplication notes
            for note in sanitized.notes:
                logger.info("extra_args sanitized", extra={"note": note})

            run_args = sanitized.cleaned_args
            run_env = env_vars
            fail_under: Optional[float] = None
            if coverage:
                temp_dir = tempfile.mkdtemp(prefix="pytest_cov_")
                cov_args, cov_env = coverage_args(sources, temp_dir)
                run_args = sanitized.cleaned_args + cov_args
                run_env = {**(env_vars or {}), **cov_env}
                fail_under = read_fail_under(interpreter, project_dir)

            # Run pytest
            test_results = check_code_with_pytest(
                project_dir=project_dir,
                test_folder=context.test_folder,
                python_executable=interpreter,
                markers=markers,
                verbosity=sanitized.verbosity,
                extra_args=run_args,
                env_vars=run_env,
                venv_bin=str(context.environment.bin_dir),
                keep_temp_files=context.keep_temp_files,
                skip_default_test_folder=sanitized.has_path_args,
                timeout_seconds=context.resolve_timeout("pytest", timeout_seconds),
            )

            # Always show detailed failure output
            result = checker_tools._format_pytest_result_with_details(
                test_results, show_details=True, show_output=sanitized.show_output
            )

            # Prepend deduplication notes so LLM can self-correct
            if sanitized.notes:
                notes_text = "\n".join(sanitized.notes)
                result = f"{notes_text}\n\n{result}"

            summary = test_results.get("summary", {})
            if temp_dir is not None:
                data = read_coverage_report(temp_dir)
                if data is None:
                    digest = "Coverage report was not produced."
                else:
                    selection = selection_line(
                        markers,
                        sanitized.cleaned_args,
                        sanitized.path_args,
                        get_pytest_addopts(project_dir),
                    )
                    digest = format_coverage_digest(
                        data,
                        selection,
                        max_modules=max_modules,
                        fail_under=fail_under,
                        tests_failed=bool(
                            (summary.get("failed") or 0) or (summary.get("error") or 0)
                        ),
                    )
                result = f"{result}\n\n{digest}"

            if test_results.get("success"):
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
                    "project_dir": project_dir,
                },
            )
            return error_msg
        finally:
            if temp_dir is not None and not context.keep_temp_files:
                shutil.rmtree(temp_dir, ignore_errors=True)
