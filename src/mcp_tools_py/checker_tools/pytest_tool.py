"""Pytest MCP tool registration."""

import logging
import shutil
import tempfile
from typing import TYPE_CHECKING, Dict, List, Optional

from mcp_tools_py.code_checker_pytest.coverage import (
    coverage_args,
    format_coverage_digest,
    no_report_message,
    read_coverage_report,
    read_fail_under,
    selection_identity,
    selection_line,
)
from mcp_tools_py.code_checker_pytest.coverage_store import (
    CoverageRun,
    finish_coverage_run,
    format_last_run,
    start_coverage_run,
)
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.utils import sanitize_extra_args
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.environment_info import get_environment_info
from mcp_tools_py.utils.project_config import (
    get_pytest_addopts,
    resolve_coverage_source,
)
from mcp_tools_py.utils.report_budget import TOOL_LINES

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
        use_last_coverage_run: bool = False,
        combine_with_previous: bool = False,
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
                a per-package table, modules ranked by missing statements with
                per-function line ranges, modules with nothing covered, and the
                test selection the numbers come from. The project's `fail_under` is not
                applied. Exclude code with coverage's own `omit` setting or
                `# pragma: no cover`.
            coverage_source: Directories to measure. Defaults to the project's
                source directories from pyproject.toml, excluding test paths.
                With use_last_coverage_run, directories to narrow the digest to;
                anything outside what was measured is refused.
            max_modules: How many modules the coverage digest's gap ranking
                details; 0 shows only the overview (default: 10).
            use_last_coverage_run: Run no tests and return the digest of the last
                coverage run, or "stale — rerun" when a Python file in scope has
                changed since. Only coverage_source and max_modules can be combined
                with it; other arguments are refused.
            combine_with_previous: Merge this coverage run with the saved runs, so
                the digest covers every selection; requires coverage=True. A rerun
                of an identical selection replaces its earlier data. When a Python
                file in scope or coverage_source changed, or the merge fails, the
                saved runs are discarded and the reply says so. A run with no
                report leaves them unchanged.

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

            # Drill into the last coverage run without rerunning tests
            run_pytest_check(use_last_coverage_run=True, coverage_source=["src/pkg"])

            # Add a second selection to the last coverage run
            run_pytest_check(
                coverage=True,
                combine_with_previous=True,
                extra_args=["tests/test_other.py"],
            )
        """
        if use_last_coverage_run:
            conflicts = [
                name
                for name, given in (
                    ("markers", bool(markers)),
                    ("extra_args", bool(extra_args)),
                    ("env_vars", bool(env_vars)),
                    ("timeout_seconds", timeout_seconds is not None),
                    ("combine_with_previous", combine_with_previous),
                    ("coverage", coverage),
                )
                if given
            ]
            if conflicts:
                return (
                    "Error: use_last_coverage_run=True cannot be used with: "
                    f"{', '.join(conflicts)}."
                )
            return format_last_run(
                str(context.project_dir), coverage_source, max_modules
            )

        if combine_with_previous and not coverage:
            return "Error: combine_with_previous=True requires coverage=True."

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
            coverage_run: Optional[CoverageRun] = None
            run_timeout = context.resolve_timeout("pytest", timeout_seconds)
            if coverage:
                temp_dir = tempfile.mkdtemp(prefix="pytest_cov_")
                cov_args, cov_env = coverage_args(sources, temp_dir)
                run_args = sanitized.cleaned_args + cov_args
                run_env = {**(env_vars or {}), **cov_env}
                fail_under = read_fail_under(interpreter, project_dir)
                addopts = get_pytest_addopts(project_dir)
                coverage_run = start_coverage_run(
                    project_dir,
                    temp_dir,
                    context.test_folder,
                    coverage_source,
                    sources,
                    fail_under,
                    selection_line(
                        markers,
                        sanitized.cleaned_args,
                        sanitized.path_args,
                        addopts,
                    ),
                    selection_identity(
                        markers,
                        sanitized.cleaned_args,
                        sanitized.path_args,
                        addopts,
                        env_vars,
                    ),
                    interpreter,
                    env_vars,
                    run_timeout,
                    combine_with_previous,
                )

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
                timeout_seconds=run_timeout,
            )

            summary = test_results.get("summary", {})
            verdict = test_results["verdict"]
            # The digest is built first so the failure section gets what is left
            digest: Optional[str] = None
            if coverage_run is not None:
                report = test_results.get("test_results")
                # Without a parsed report, JSON from import-time lines proves nothing.
                data = (
                    read_coverage_report(coverage_run.temp_dir)
                    if report is not None
                    else None
                )
                finished = finish_coverage_run(coverage_run, data, report, verdict)
                if finished.data is None:
                    digest = no_report_message(finished.outcome["failed_collectors"])
                else:
                    digest = format_coverage_digest(
                        finished.data,
                        finished.selection,
                        max_modules=max_modules,
                        fail_under=fail_under,
                        **finished.outcome,
                    )
                digest = "\n".join([digest, *finished.notes])

            max_lines = TOOL_LINES
            if digest is not None:
                max_lines = max(TOOL_LINES // 2, TOOL_LINES - digest.count("\n") - 1)

            # Always show detailed failure output
            result = checker_tools._format_pytest_result_with_details(
                test_results,
                show_details=True,
                show_output=sanitized.show_output,
                collect_only=sanitized.collect_only,
                max_lines=max_lines,
            )

            # Prepend the test-paths and deduplication notes so LLM can self-correct
            test_paths_note = test_results.get("test_paths_note")
            notes = [*([test_paths_note] if test_paths_note else []), *sanitized.notes]
            if notes:
                notes_text = "\n".join(notes)
                result = f"{notes_text}\n\n{result}"
            if digest is not None:
                result = f"{result}\n\n{digest}"

            if verdict.status in (RunStatus.PASSED, RunStatus.FAILED):
                logger.info(
                    "Pytest execution completed",
                    extra={
                        "passed": summary.get("passed", 0) or 0,
                        "failed": summary.get("failed", 0) or 0,
                        "errors": summary.get("error", 0) or 0,
                        "duration": summary.get("duration", 0) or 0,
                        "status": verdict.status.value,
                    },
                )
            elif verdict.status is RunStatus.SUSPICIOUS:
                logger.warning(
                    "Pytest run reported no outcomes",
                    extra={"collected": summary.get("collected", 0) or 0},
                )
            else:
                logger.error(
                    "Pytest execution failed",
                    extra={
                        "problems": verdict.problems,
                        "exit_code": verdict.exit_code,
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
