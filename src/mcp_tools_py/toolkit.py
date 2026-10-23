"""PythonToolkit: the mcp-coder entry point for Python projects.

Registered under the ``mcp_coder.toolkits`` entry-point group so mcp-coder
discovers and runs it without naming any of mcp-tools-py's other modules.
``run`` calls the existing runners/parsers directly — never the
``checker_tools/*`` MCP tool functions, which format LLM-facing prose
instead of returning structured data.
"""

import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mcp_coder_utils.toolkit import (
    ActionRequest,
    ActionResult,
    Finding,
    Toolkit,
    ToolkitInfo,
    VerifyItem,
)

from mcp_tools_py.code_checker_pytest.coverage import (
    coverage_args,
    format_coverage_digest,
    read_coverage_report,
    read_fail_under,
    selection_line,
)
from mcp_tools_py.code_checker_pytest.models import PytestReport, Test
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.formatter.runner import (
    resolve_steps,
    run_format_code,
    step_tool,
    validate_steps,
)
from mcp_tools_py.toolkit_checks import _result_from_findings, _run_check
from mcp_tools_py.utils.project_config import (
    get_pytest_addopts,
    resolve_coverage_source,
    resolve_target_directories,
)
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.tool_context import CONSOLE_SCRIPT_TOOLS, ToolContext

_FAILED_OUTCOMES = ("failed", "error")

_FIX_CHECK_PROMPT = """\
Fix the mypy type errors shown in the output below.

Focus only on resolving the type errors - do not make unnecessary changes to the code.

For each error:
1. Understand the type mismatch or missing annotation
2. Add appropriate type hints or fix incorrect types
3. Use proper typing imports (List, Dict, Optional, etc.) from typing module
4. Ensure all function parameters and return types are properly annotated

Keep changes minimal and focused on type correctness.

Expected output: Code changes that resolve all type errors while maintaining functionality.
"""


def _build_context(project_dir: Path) -> ToolContext:
    """Build the ToolContext PythonToolkit runs its actions against.

    Mirrors the old mcp_coder/mcp_tools_py.py shim: no python_executable or
    venv_path override, since mcp-coder runs inside the project's own venv.

    Returns:
        A context over `project_dir`'s own resolved Python environment.
    """
    return ToolContext(project_dir=project_dir, environment=PythonEnvironment.resolve())


def _test_failure_summary(test: Test) -> str:
    """One-line failure summary for a failing or erroring pytest Finding.

    Returns:
        The call stage's crash message, falling back to the setup stage's,
        falling back to the bare outcome.
    """
    if test.call and test.call.crash:
        return test.call.crash.message
    if test.setup and test.setup.crash:
        return test.setup.crash.message
    return test.outcome


def _run_test(context: ToolContext, depth: str) -> ActionResult:
    """Run pytest at `depth` and map the outcome onto an ActionResult.

    `full` additionally measures coverage and sets `raw` to the digest
    (mirroring `run_pytest_check(coverage=True)`); a `fail_under` miss is
    informational only and never changes `status`.

    Returns:
        "error" if pytest is unavailable, or the run failed for a reason
        other than "no tests found"; "skipped" for no tests found;
        "findings" with one Finding per failing/erroring test; else "ok".
    """
    if not context.is_tool_available("pytest"):
        return ActionResult(
            status="error", summary=context.unavailable_message("pytest")
        )

    project_dir = str(context.project_dir)
    interpreter = str(context.environment.interpreter)
    markers = ["not integration"] if depth == "quick" else None

    extra_args: list[str] = []
    env_vars: dict[str, str] = {}
    fail_under: float | None = None
    temp_dir: str | None = None
    if depth == "full":
        sources = resolve_coverage_source(project_dir, None)
        if isinstance(sources, str):
            return ActionResult(status="error", summary=sources)
        temp_dir = tempfile.mkdtemp(prefix="pytest_cov_")
        cov_args, cov_env = coverage_args(sources, temp_dir)
        extra_args = cov_args
        env_vars = cov_env
        fail_under = read_fail_under(interpreter, project_dir)

    try:
        result = check_code_with_pytest(
            project_dir,
            python_executable=interpreter,
            test_folder=context.test_folder,
            markers=markers,
            extra_args=extra_args or None,
            env_vars=env_vars or None,
            venv_bin=str(context.environment.bin_dir),
            keep_temp_files=context.keep_temp_files,
            timeout_seconds=context.resolve_timeout("pytest"),
        )

        if not result["success"]:
            error_message: str = result["error"]
            if "No Tests Found" in error_message:
                return ActionResult(status="skipped", summary=error_message)
            return ActionResult(status="error", summary=error_message)

        report: PytestReport = result["test_results"]
        summary_text: str = result["summary_text"]
        findings = [
            Finding(
                key=test.nodeid,
                message=_test_failure_summary(test),
                path=test.nodeid.split("::")[0],
            )
            for test in report.tests or []
            if test.outcome in _FAILED_OUTCOMES
        ]
        action_result = _result_from_findings(
            error=None,
            findings=findings,
            ok_summary=summary_text,
            findings_summary=summary_text,
        )

        if depth == "full" and temp_dir is not None:
            data = read_coverage_report(temp_dir)
            if data is not None:
                selection = selection_line(
                    markers, [], [], get_pytest_addopts(project_dir)
                )
                action_result.raw = format_coverage_digest(
                    data,
                    selection,
                    fail_under=fail_under,
                    tests_failed=bool(findings),
                )
        return action_result
    finally:
        if temp_dir is not None and not context.keep_temp_files:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _run_format(context: ToolContext, depth: str) -> ActionResult:
    """Run the formatter at `depth` and map the outcome onto an ActionResult.

    Returns:
        "error" if the formatter cannot be resolved, a formatter tool is
        unavailable, target directories cannot be resolved, or a step
        failed outside check mode; "findings" with one Finding per path
        that would be reformatted in check mode; else "ok".
    """
    check_only = depth == "check"
    project_dir = context.project_dir

    try:
        steps = resolve_steps(project_dir)
        validate_steps(steps)
    except ValueError as exc:
        return ActionResult(status="error", summary=str(exc))

    for step in steps:
        tool = step_tool(step)
        if not context.is_tool_available(tool):
            return ActionResult(
                status="error", summary=context.unavailable_message(tool)
            )

    dirs = resolve_target_directories(str(project_dir), None)
    if isinstance(dirs, str):
        return ActionResult(status="error", summary=dirs)

    timeouts = {step: context.resolve_timeout(step_tool(step)) for step in steps}
    results = run_format_code(
        str(context.environment.interpreter),
        project_dir,
        dirs,
        steps,
        check_only,
        timeouts=timeouts,
        environment=context.tool_environment,
    )
    raw = "\n\n".join(result.output for result in results.values())

    broken = [
        step
        for step, result in results.items()
        if result.unparsable_files or (not result.success and not check_only)
    ]
    if broken:
        action_result = ActionResult(
            status="error",
            summary=f"Formatting failed in step(s): {', '.join(broken)}",
        )
        action_result.raw = raw
        return action_result

    changed = sorted(
        {path for result in results.values() for path in result.files_changed}
    )
    findings = (
        [
            Finding(
                key=f"format|check|{path}",
                message=f"{path} needs reformatting",
                path=path,
            )
            for path in changed
        ]
        if check_only
        else []
    )
    action_result = _result_from_findings(
        error=None,
        findings=findings,
        ok_summary="Formatting is up to date.",
        findings_summary=f"{len(changed)} file(s) need reformatting.",
    )
    action_result.raw = raw
    return action_result


class PythonToolkit(Toolkit):
    """mcp-coder's Python toolkit: runs mcp-tools-py's checkers directly."""

    def describe(self, config: Mapping[str, Any]) -> ToolkitInfo:
        """Describe PythonToolkit's actions, depths and LLM permissions.

        `run` only handles `test` so far; `format`/`check` are declared here
        regardless, since this is static data, not tied to `run`'s current
        completeness.

        Returns:
            The final ToolkitInfo for all three actions.
        """
        del config
        return ToolkitInfo(
            actions={
                "format": ["apply", "check"],
                "check": ["quick", "standard", "full"],
                "test": ["quick", "standard", "full"],
            },
            params_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            llm_permissions={
                "format": {
                    depth: ["mcp__mcp-tools-py__run_format_code"]
                    for depth in ("apply", "check")
                },
                "check": {
                    "quick": ["mcp__mcp-tools-py__run_mypy_check"],
                    "standard": [
                        "mcp__mcp-tools-py__run_mypy_check",
                        "mcp__mcp-tools-py__run_pylint_check",
                    ],
                    "full": [
                        "mcp__mcp-tools-py__run_mypy_check",
                        "mcp__mcp-tools-py__run_pylint_check",
                        "mcp__mcp-tools-py__run_vulture_check",
                        "mcp__mcp-tools-py__run_lint_imports_check",
                        "mcp__mcp-tools-py__run_tach_check",
                        "mcp__mcp-tools-py__run_ruff_check",
                        "mcp__mcp-tools-py__run_bandit_check",
                        "mcp__mcp-tools-py__run_deptry_check",
                    ],
                },
                "test": {
                    depth: ["mcp__mcp-tools-py__run_pytest_check"]
                    for depth in ("quick", "standard", "full")
                },
            },
        )

    def run(self, request: ActionRequest) -> ActionResult:
        """Run one action at one depth.

        Returns:
            The action outcome.

        Raises:
            NotImplementedError: For any action other than "test", "format",
                and "check".
        """
        context = _build_context(request.project_dir)
        if request.action == "test":
            return _run_test(context, request.depth)
        if request.action == "format":
            return _run_format(context, request.depth)
        if request.action == "check":
            return _run_check(context, request.depth)
        raise NotImplementedError(request.action)

    def verify(self, project_dir: Path) -> list[VerifyItem]:
        """Check that every tool this toolkit drives is available.

        Returns:
            One VerifyItem per console-script tool, per `python -m` tool
            (mypy, pylint, pytest), and one more named "formatter" for
            whether a formatter can be resolved for `project_dir`.
        """
        context = _build_context(project_dir)
        items: list[VerifyItem] = []
        for tool in sorted(CONSOLE_SCRIPT_TOOLS | {"mypy", "pylint", "pytest"}):
            ok = context.is_tool_available(tool)
            items.append(
                VerifyItem(
                    name=tool,
                    status="ok" if ok else "error",
                    message="" if ok else context.unavailable_message(tool),
                )
            )
        try:
            resolve_steps(project_dir)
            items.append(VerifyItem(name="formatter", status="ok"))
        except ValueError as exc:
            items.append(VerifyItem(name="formatter", status="error", message=str(exc)))
        return items

    def prompt_fragments(self) -> dict[str, str]:
        """Prompt text PythonToolkit contributes to mcp-coder's prompts.

        Returns:
            `language_context`, `check_instructions`, and `fix.check` — the
            Mypy Fix prompt, with its `[mypy_output]` placeholder dropped
            since the actual output now travels via `ActionResult.fix_text`.
        """
        return {
            "language_context": "This is a Python project.",
            "check_instructions": (
                "Run pylint, mypy and pytest via the MCP tools. At full depth, "
                "also run the other checkers, including deptry."
            ),
            "fix.check": _FIX_CHECK_PROMPT,
        }
