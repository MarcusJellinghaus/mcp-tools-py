"""PythonToolkit: the mcp-coder entry point for Python projects.

Registered under the ``mcp_coder.toolkits`` entry-point group so mcp-coder
discovers and runs it without naming any of mcp-tools-py's other modules.
``run`` calls the existing runners/parsers directly — never the
``checker_tools/*`` MCP tool functions, which format LLM-facing prose
instead of returning structured data.
"""

import json
import os
import re
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

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
    selection_identity,
    selection_line,
)
from mcp_tools_py.code_checker_pytest.coverage_store import (
    CoverageRun,
    FinishedRun,
    finish_coverage_run,
    start_coverage_run,
)
from mcp_tools_py.code_checker_pytest.models import PytestReport, Test
from mcp_tools_py.code_checker_pytest.reporting import (
    XDIST_MARKER,
    collectors_failed_line,
)
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.verdict import (
    XDIST_HINT,
    RunStatus,
    RunVerdict,
    cap_problems,
    format_error_text,
    format_suspicious_text,
)
from mcp_tools_py.formatter.runner import (
    resolve_steps,
    run_format_code,
    step_tool,
    validate_steps,
)
from mcp_tools_py.toolkit_checks import (
    _CHECK_DEPTHS,
    _result_from_findings,
    _run_check,
)
from mcp_tools_py.utils.environment_info import TOOL_MODULES
from mcp_tools_py.utils.project_config import (
    get_pytest_addopts,
    resolve_coverage_source,
    resolve_target_directories,
)
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import execute_command
from mcp_tools_py.utils.tool_context import ToolContext

_FAILED_OUTCOMES = ("failed", "error")
_XDIST_KEY = "pytest|collection|xdist"
# pytest: "Interrupted: N error(s) during collection"
_COLLECTION_INTERRUPTED = "during collection"

# Same list as mcp-coder's workflows/rebase_automated.py::AUTOMATED_EXCLUDED_MARKERS;
# this is the single home of the list.
UNATTENDED_EXCLUDED_MARKERS: list[str] = [
    "not claude_cli_integration",
    "not copilot_cli_integration",
    "not langchain_integration",
    "not llm_integration",
    "not jenkins_integration",
    "not install_integration",
]
# Stops --strict-markers projects rejecting marker names they don't register.
_STRICT_MARKERS_OFF: list[str] = ["-o", "strict_markers=false"]
_LONG_TEST_TIMEOUT = 1800  # seconds; test@standard, @unattended and @full
# One line per marker in `pytest --markers`: "@pytest.mark.<name>[(<args>)]: <desc>"
_MARKER_LINE = re.compile(r"^@pytest\.mark\.([^(:\s]+)", re.MULTILINE)
_MARKER_READ_FAILED = "Could not read the project's pytest markers"

_FIX_CHECK_PROMPT = """\
Fix the findings reported by the checkers in the output below \
(type checker, linter or other static checks).

Fix only the reported findings - do not make unnecessary changes to the code.

For each finding:
1. Read the message and the code it points at
2. Fix the cause in the code rather than silencing the checker

Keep changes minimal and focused.

Expected output: Code changes that resolve all reported findings while maintaining functionality.
"""

_FIX_TEST_PROMPT = """\
Fix the failing tests named in the output below.

For each failure, find the cause and fix whichever is wrong - the code or the test.
Keep changes minimal and focused; do not change unrelated code or tests.

Re-run only the failing tests named in the output to confirm the fix, not the whole suite.

Expected output: Code or test changes that make the failing tests pass while maintaining functionality.
"""


def _build_context(project_dir: Path) -> ToolContext:
    """Build the ToolContext PythonToolkit runs its actions against.

    The project environment comes from VIRTUAL_ENV when it is set and
    non-empty, else from sys.executable: mcp-coder can run from its own tool
    env, while the shell's activated venv is the project's. A VIRTUAL_ENV
    without an interpreter is an error, never a fallback. `tool_environment`
    keeps its sys.executable default.

    Returns:
        A context over the resolved project Python environment.

    Raises:
        FileNotFoundError: VIRTUAL_ENV is set but has no interpreter; the
            message names VIRTUAL_ENV.
    """
    venv = os.environ.get("VIRTUAL_ENV")
    if not venv:
        return ToolContext(
            project_dir=project_dir, environment=PythonEnvironment.resolve()
        )
    try:
        environment = PythonEnvironment.resolve(venv_path=venv)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"VIRTUAL_ENV is set to {venv}, but it has no Python interpreter. "
            "Activate the project's environment or unset VIRTUAL_ENV."
        ) from exc
    return ToolContext(project_dir=project_dir, environment=environment)


def _tool_item(context: ToolContext, tool: str) -> VerifyItem:
    """Report whether `tool` is available in `context`.

    Returns:
        An "ok" VerifyItem, or an "error" one carrying the standard
        "tool not available" message.
    """
    ok = context.is_tool_available(tool)
    return VerifyItem(
        name=tool,
        status="ok" if ok else "error",
        message="" if ok else context.unavailable_message(tool),
    )


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


def _collector_findings(report: PytestReport) -> list[Finding]:
    """One Finding per failed collector; xdist mismatches collapse into one.

    Returns:
        A Finding per distinct failed collector node id, keyed by it, whose
        message is the last non-empty `longrepr` line; then, if any collector
        failed with an xdist collection mismatch, one `_XDIST_KEY` Finding
        without a path carrying `XDIST_HINT`.
    """
    by_id: dict[str, Finding] = {}
    xdist: Finding | None = None
    for collector in report.collectors or []:
        if collector.outcome not in _FAILED_OUTCOMES:
            continue
        text = collector.longrepr or ""
        if XDIST_MARKER in text:
            xdist = xdist or Finding(
                key=_XDIST_KEY, message=f"{XDIST_MARKER}\n{XDIST_HINT}"
            )
        elif collector.nodeid not in by_id:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            by_id[collector.nodeid] = Finding(
                key=collector.nodeid,
                message=lines[-1] if lines else "collection failed",
                path=collector.nodeid.split("::")[0],
            )
    return [*by_id.values(), *([xdist] if xdist else [])]


def _is_collection_error(report: PytestReport, verdict: RunVerdict) -> bool:
    """True when an ERROR verdict was caused by collection errors.

    Exit code 1 (tests failed) without any failed/errored test means only
    collectors failed. Exit code 2 is also pytest's KeyboardInterrupt code,
    so it additionally needs pytest's "during collection" line.

    Returns:
        Whether `verdict` is an ERROR that collection errors explain.
    """
    if verdict.status is not RunStatus.ERROR:
        return False
    if verdict.exit_code == 1:
        return True
    output = report.error_context.error_message if report.error_context else ""
    return verdict.exit_code == 2 and _COLLECTION_INTERRUPTED in output


def _with_note(result: ActionResult, note: str | None) -> ActionResult:
    """Prepend `note` to the summary of `result`.

    Returns:
        `result`, its summary led by `note` and a blank line when `note` is set.
    """
    if note:
        result.summary = f"{note}\n\n{result.summary}"
    return result


def _registered_markers(context: ToolContext) -> list[str] | str:
    """Names of the markers registered in the project, read via `pytest --markers`.

    Returns:
        The marker names, or an error message when the list can't be read:
        timeout, run failure, non-zero exit, or exit 0 with no marker lines
        (pytest's built-in markers always print, so no lines means the output
        wasn't understood).
    """
    timeout_seconds = context.resolve_timeout("pytest")
    # Same PATH as the real run's venv_bin, so conftest.py loads alike.
    venv_bin = str(context.environment.bin_dir)
    result = execute_command(
        [
            str(context.environment.interpreter),
            "-m",
            "pytest",
            "--markers",
            "--color=no",
        ],
        cwd=str(context.project_dir),
        timeout_seconds=timeout_seconds,
        env={"PATH": f"{venv_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
    )
    if result.timed_out:
        return f"{_MARKER_READ_FAILED}: timed out after {timeout_seconds} seconds."
    if result.execution_error:
        return f"{_MARKER_READ_FAILED}: {result.execution_error}"
    if result.return_code != 0:
        output = (result.stderr or result.stdout).strip()
        tail = "\n".join(output.splitlines()[-20:])
        return f"{_MARKER_READ_FAILED}: exit code {result.return_code}\n{tail}"
    names = [name.strip() for name in _MARKER_LINE.findall(result.stdout)]
    return names or f"{_MARKER_READ_FAILED}: no marker lines in the output."


def _run_test(context: ToolContext, depth: str) -> ActionResult:
    """Run pytest at `depth` and map the outcome onto an ActionResult.

    `full` additionally measures coverage, saves or clears the saved coverage
    data, and sets `raw` to the digest (mirroring
    `run_pytest_check(coverage=True)`); a `fail_under` miss is informational
    only and never changes `status`.

    `quick` excludes every registered marker whose name ends in
    `integration`, read via `_registered_markers`; with none registered it
    runs unfiltered. A failed marker read is `error`, never an unfiltered run.

    Every depth but `quick` defaults the pytest timeout to
    `_LONG_TEST_TIMEOUT`; `pytest-timeout` and `check-timeout` in
    `[tool.mcp-tools-py]` still win.

    Failed collectors become findings too, also when collection errors
    alone made the verdict ERROR (exit 1, or exit 2 "during collection").

    Returns:
        "error" if pytest is unavailable, `quick` can't read the registered
        markers, the verdict is ERROR (other than
        "no tests found" or one caused by failed collectors), or FAILED
        without any failing/erroring test or collector; "skipped" for no
        tests found; "findings" with one Finding per failing/erroring test
        and per failed collector (one for all xdist mismatches); "ok" for
        PASSED, and for SUSPICIOUS with a "Not verified" summary.
    """
    if not context.is_tool_available("pytest"):
        return ActionResult(
            status="error", summary=context.unavailable_message("pytest")
        )
    if depth != "quick":
        context = replace(context, check_timeout=_LONG_TEST_TIMEOUT)

    project_dir = str(context.project_dir)
    interpreter = str(context.environment.interpreter)
    markers = list(UNATTENDED_EXCLUDED_MARKERS) if depth == "unattended" else None
    if depth == "quick":
        names = _registered_markers(context)
        if isinstance(names, str):
            return ActionResult(status="error", summary=names)
        markers = [f"not {n}" for n in names if n.endswith("integration")] or None

    extra_args = list(_STRICT_MARKERS_OFF) if depth == "unattended" else []
    env_vars: dict[str, str] = {}
    fail_under: float | None = None
    temp_dir: str | None = None
    coverage_run: CoverageRun | None = None
    try:
        if depth == "full":
            sources = resolve_coverage_source(project_dir, None)
            if isinstance(sources, str):
                return ActionResult(status="error", summary=sources)
            temp_dir = tempfile.mkdtemp(prefix="pytest_cov_")
            cov_args, cov_env = coverage_args(sources, temp_dir)
            extra_args.extend(cov_args)
            env_vars = cov_env
            fail_under = read_fail_under(interpreter, project_dir)
            addopts = get_pytest_addopts(project_dir)
            coverage_run = start_coverage_run(
                project_dir,
                temp_dir,
                context.test_folder,
                None,
                sources,
                fail_under,
                selection_line(markers, [], [], addopts),
                selection_identity(markers, [], [], addopts, None),
                interpreter,
                None,
                context.resolve_timeout("pytest"),
            )

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

        note: str | None = result.get("test_paths_note")
        verdict: RunVerdict = result["verdict"]
        report: PytestReport | None = result.get("test_results")
        finished: FinishedRun | None = None
        if coverage_run is not None:
            # Without a parsed report, JSON from import-time lines proves nothing.
            data = (
                read_coverage_report(coverage_run.temp_dir)
                if report is not None
                else None
            )
            finished = finish_coverage_run(coverage_run, data, report, verdict)

        # Before the `known` gate: a real collection failure arrives as ERROR.
        collector_findings = _collector_findings(report) if report else []
        collection_error = report is not None and _is_collection_error(report, verdict)
        known = (RunStatus.PASSED, RunStatus.FAILED, RunStatus.SUSPICIOUS)
        if report is None or (
            verdict.status not in known
            and not (collection_error and collector_findings)
        ):
            if any("No Tests Found" in p for p in verdict.problems):
                return _with_note(
                    ActionResult(status="skipped", summary="\n".join(verdict.problems)),
                    note,
                )
            return _with_note(
                ActionResult(
                    status="error", summary=format_error_text(report, verdict)
                ),
                note,
            )

        summary_text: str = result["summary_text"]
        findings = [
            *(
                Finding(
                    key=test.nodeid,
                    message=_test_failure_summary(test),
                    path=test.nodeid.split("::")[0],
                )
                for test in report.tests or []
                if test.outcome in _FAILED_OUTCOMES
            ),
            *collector_findings,
        ]
        count_line = collectors_failed_line(report)
        count_text = f"{count_line}\n\n" if count_line else ""
        failed_summary = (
            f"{summary_text}\n\n{count_text}{cap_problems(verdict.problems)}"
        )
        if verdict.status is RunStatus.FAILED and not findings:
            return _with_note(
                ActionResult(status="error", summary=failed_summary), note
            )
        ok_summary = (
            format_suspicious_text(report.summary.collected, report.summary.deselected)
            if verdict.status is RunStatus.SUSPICIOUS
            else summary_text
        )
        action_result = _result_from_findings(
            error=None,
            findings=findings,
            ok_summary=ok_summary,
            findings_summary=failed_summary if count_line else summary_text,
            # Node ids for tests and collectors; the xdist finding has no path.
            locations=[f.key if f.path else None for f in findings],
        )

        if finished is not None and finished.data is not None:
            digest = format_coverage_digest(
                finished.data,
                finished.selection,
                fail_under=fail_under,
                **finished.outcome,
            )
            action_result.raw = "\n".join([digest, *finished.notes])
        return _with_note(action_result, note)
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

    def describe(self) -> ToolkitInfo:
        """Describe PythonToolkit's actions, depths and LLM permissions.

        `run` only handles `test` so far; `format`/`check` are declared here
        regardless, since this is static data, not tied to `run`'s current
        completeness.

        Returns:
            The final ToolkitInfo for all three actions.
        """
        return ToolkitInfo(
            actions={
                "format": ["apply", "check"],
                "check": ["quick", "standard", "full"],
                "test": ["quick", "standard", "unattended", "full"],
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
                    for depth in ("quick", "standard", "unattended", "full")
                },
            },
        )

    def run(self, request: ActionRequest) -> ActionResult:
        """Run one action at one depth.

        Returns:
            The action outcome; status "error" for an action or depth that
            `describe` doesn't declare, or when VIRTUAL_ENV is set but has no
            interpreter.
        """
        actions = self.describe().actions
        depths = actions.get(request.action)
        if depths is None:
            return ActionResult(
                status="error",
                summary=f"Unknown action '{request.action}'; "
                f"declared: {', '.join(actions)}.",
            )
        if request.depth not in depths:
            return ActionResult(
                status="error",
                summary=f"Unknown depth '{request.depth}' for action "
                f"'{request.action}'; declared: {', '.join(depths)}.",
            )
        try:
            context = _build_context(request.project_dir)
        except FileNotFoundError as exc:
            return ActionResult(status="error", summary=str(exc))
        if request.action == "test":
            return _run_test(context, request.depth)
        if request.action == "format":
            return _run_format(context, request.depth)
        return _run_check(context, request.depth)

    def verify(self, project_dir: Path, action: str | None = None) -> list[VerifyItem]:
        """Check that the tools `action` drives are available.

        - None: every tool, plus "formatter".
        - "format": "formatter" plus the tools of the resolved formatter
          steps (none when no formatter resolves).
        - "check": the tools of the `full` check depth.
        - "test": pytest.

        Returns:
            One VerifyItem per tool, plus one named "formatter" for whether a
            formatter can be resolved for `project_dir`; a single "error"
            item named after `action` when `describe` doesn't declare it; a
            single "error" item named "environment" when VIRTUAL_ENV is set
            but has no interpreter.
        """
        actions = self.describe().actions
        if action is not None and action not in actions:
            return [
                VerifyItem(
                    name=action,
                    status="error",
                    message=f"Unknown action '{action}'; "
                    f"declared: {', '.join(actions)}.",
                )
            ]
        try:
            context = _build_context(project_dir)
        except FileNotFoundError as exc:
            return [VerifyItem(name="environment", status="error", message=str(exc))]
        per_action = {"test": ["pytest"], "check": list(_CHECK_DEPTHS["full"])}
        tools = per_action.get(action or "", sorted(TOOL_MODULES))
        formatter_items: list[VerifyItem] = []
        if action in (None, "format"):
            try:
                steps = resolve_steps(project_dir)
                formatter_items.append(VerifyItem(name="formatter", status="ok"))
                if action == "format":
                    tools = sorted({step_tool(step) for step in steps})
            except ValueError as exc:
                formatter_items.append(
                    VerifyItem(name="formatter", status="error", message=str(exc))
                )
                if action == "format":
                    tools = []
        return [_tool_item(context, tool) for tool in tools] + formatter_items

    def prompt_fragments(self) -> dict[str, str]:
        """Prompt text PythonToolkit contributes to mcp-coder's prompts.

        Returns:
            `language_context`, `check_instructions`,
            `check_instructions.unattended` — the pytest marker filter of the
            `unattended` test depth — `fix.check` — fix the findings of any
            checker — and `fix.test` — fix the failing tests and re-run only
            those. Neither fix prompt has a placeholder: the actual output
            travels via `ActionResult.fix_text`.
        """
        names = ", ".join(m.removeprefix("not ") for m in UNATTENDED_EXCLUDED_MARKERS)
        return {
            "language_context": "This is a Python project.",
            "check_instructions": (
                "Run pylint, mypy and pytest via the MCP tools. At full depth, "
                "also run the other checkers, including deptry."
            ),
            "check_instructions.unattended": (
                "When you run `mcp__mcp-tools-py__run_pytest_check`, pass "
                f"markers={json.dumps(UNATTENDED_EXCLUDED_MARKERS)} and "
                f"extra_args={json.dumps(_STRICT_MARKERS_OFF)}. This deselects "
                f"tests marked {names}; the -o option stops projects using "
                "--strict-markers from rejecting marker names they do not "
                "register."
            ),
            "fix.check": _FIX_CHECK_PROMPT,
            "fix.test": _FIX_TEST_PROMPT,
        }
