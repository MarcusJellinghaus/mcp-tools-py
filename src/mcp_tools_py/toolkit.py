"""PythonToolkit: the mcp-coder entry point for Python projects.

Registered under the ``mcp_coder.toolkits`` entry-point group so mcp-coder
discovers and runs it without naming any of mcp-tools-py's other modules.
``run`` calls the existing runners/parsers directly — never the
``checker_tools/*`` MCP tool functions, which format LLM-facing prose
instead of returning structured data.
"""

import shutil
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from mcp_coder_utils.toolkit import (
    ActionRequest,
    ActionResult,
    Finding,
    Toolkit,
    ToolkitInfo,
)

from mcp_tools_py.code_checker_bandit.runners import run_bandit_check_impl
from mcp_tools_py.code_checker_lint_imports.runners import run_lint_imports_check_impl
from mcp_tools_py.code_checker_mypy.runners import run_mypy_check
from mcp_tools_py.code_checker_pylint.runners import get_pylint_results
from mcp_tools_py.code_checker_pytest.coverage import (
    coverage_args,
    format_coverage_digest,
    read_coverage_report,
    read_fail_under,
    selection_line,
)
from mcp_tools_py.code_checker_pytest.models import PytestReport, Test
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_vulture.runners import run_vulture_check
from mcp_tools_py.formatter.runner import (
    resolve_steps,
    run_format_code,
    step_tool,
    validate_steps,
)
from mcp_tools_py.utils.project_config import (
    get_pytest_addopts,
    resolve_coverage_source,
    resolve_target_directories,
)
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.ruff_parsing import parse_ruff_json_output
from mcp_tools_py.utils.subprocess_runner import execute_command
from mcp_tools_py.utils.tool_context import ToolContext

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


def _finding_line(finding: Finding) -> str:
    """One bullet line for `finding`, used to build `ActionResult.fix_text`.

    Returns:
        "- path: rule: message", omitting path/rule when either is absent.
    """
    prefix = ": ".join(part for part in (finding.path, finding.rule) if part)
    return f"- {prefix}: {finding.message}" if prefix else f"- {finding.message}"


def _result_from_findings(
    error: str | None,
    findings: list[Finding],
    ok_summary: str,
    findings_summary: str,
) -> ActionResult:
    """Map a tool's error/findings outcome onto ActionResult's status rules.

    Returns:
        status="error" when `error` is set; "findings" (with `fix_text`
        built from `findings`, one bullet line each) when findings is
        non-empty; otherwise "ok".
    """
    if error is not None:
        return ActionResult(status="error", summary=error, findings=findings)
    if findings:
        fix_text = "\n".join(_finding_line(finding) for finding in findings)
        return ActionResult(
            status="findings",
            summary=findings_summary,
            findings=findings,
            fix_text=fix_text,
        )
    return ActionResult(status="ok", summary=ok_summary)


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


_STATUS_RANK: dict[str, int] = {"skipped": 0, "ok": 1, "findings": 2, "error": 3}


def _merge(results: list[ActionResult]) -> ActionResult:
    """Combine check results with worst-status-wins semantics.

    Returns:
        One ActionResult: status is the worst across `results` ("error" >
        "findings" > "ok" > "skipped"), findings and non-empty raw outputs
        concatenated, fix_text rebuilt from the merged findings.
    """
    worst = max(results, key=lambda result: _STATUS_RANK[result.status])
    findings = [finding for result in results for finding in result.findings]
    summary = "; ".join(result.summary for result in results)
    raw = "\n\n".join(result.raw for result in results if result.raw)
    fix_text = (
        "\n".join(_finding_line(finding) for finding in findings) if findings else ""
    )
    return ActionResult(
        status=worst.status,
        summary=summary,
        findings=findings,
        raw=raw,
        fix_text=fix_text,
    )


def _run_mypy(context: ToolContext, depth: str) -> ActionResult:
    """Run mypy and map the outcome onto an ActionResult.

    `depth` is accepted but unused, so the signature matches every other
    `_CHECK_RUNNERS` entry.

    Returns:
        "error" if target directories cannot be resolved or mypy itself
        errored; "findings" with one Finding per message; else "ok".
    """
    del depth
    project_dir = str(context.project_dir)
    dirs = resolve_target_directories(project_dir, None)
    if isinstance(dirs, str):
        return ActionResult(status="error", summary=dirs)

    result = run_mypy_check(
        project_dir,
        python_executable=str(context.environment.interpreter),
        target_directories=dirs,
        timeout_seconds=context.resolve_timeout("mypy"),
    )
    findings = [
        Finding(
            key=f"{message.file}|{message.code}|{message.message}",
            message=message.message,
            path=message.file,
            rule=message.code,
            severity=message.severity,
        )
        for message in result.messages
    ]
    return _result_from_findings(
        error=result.error,
        findings=findings,
        ok_summary="mypy found no issues.",
        findings_summary=f"mypy found {len(findings)} issue(s).",
    )


def _run_pylint(context: ToolContext, depth: str) -> ActionResult:
    """Run pylint and map the outcome onto an ActionResult.

    `depth` is accepted but unused, so the signature matches every other
    `_CHECK_RUNNERS` entry.

    Returns:
        "error" if target directories cannot be resolved or pylint itself
        errored; "findings" with one Finding per message; else "ok".
    """
    del depth
    project_dir = str(context.project_dir)
    dirs = resolve_target_directories(project_dir, None)
    if isinstance(dirs, str):
        return ActionResult(status="error", summary=dirs)

    result = get_pylint_results(
        project_dir,
        python_executable=str(context.environment.interpreter),
        target_directories=dirs,
        timeout_seconds=context.resolve_timeout("pylint"),
    )
    findings = [
        Finding(
            key=f"{message.path}|{message.message_id}|{message.message}",
            message=message.message,
            path=message.path,
            rule=message.message_id,
        )
        for message in result.messages
    ]
    return _result_from_findings(
        error=result.error,
        findings=findings,
        ok_summary="pylint found no issues.",
        findings_summary=f"pylint found {len(findings)} issue(s).",
    )


def _run_vulture(context: ToolContext, depth: str) -> ActionResult:
    """Run vulture and map the outcome onto an ActionResult.

    vulture's output has no stable per-location key, so a finding is
    reported once, keyed `vulture|{depth}`.

    Returns:
        "error" if target directories cannot be resolved or vulture timed
        out/failed to run; "findings" with one degraded Finding when it
        reports dead code; else "ok".
    """
    project_dir = context.project_dir
    dirs = resolve_target_directories(str(project_dir), None)
    if isinstance(dirs, str):
        return ActionResult(status="error", summary=dirs)

    binary = context.tool_environment.binary("vulture")
    if binary is None:
        return ActionResult(
            status="error", summary=context.unavailable_message("vulture")
        )

    whitelist_path = project_dir / context.vulture_whitelist
    whitelist = str(whitelist_path) if whitelist_path.exists() else None

    output = run_vulture_check(
        vulture_binary=str(binary),
        project_dir=str(project_dir),
        target_directories=dirs,
        whitelist_path=whitelist,
        timeout_seconds=context.resolve_timeout("vulture"),
    )
    if output.startswith("vulture timed out") or output.startswith(
        "vulture failed to run:"
    ):
        return ActionResult(status="error", summary=output)
    if output == "vulture produced no output.":
        return ActionResult(status="ok", summary="vulture found no issues.")

    finding = Finding(key=f"vulture|{depth}", message=output)
    return ActionResult(
        status="findings",
        summary="vulture found unused code.",
        findings=[finding],
        fix_text=output,
    )


def _run_lint_imports(context: ToolContext, depth: str) -> ActionResult:
    """Run lint-imports and map the outcome onto an ActionResult.

    lint-imports' report has no stable per-location key, so a finding is
    reported once, keyed `lint-imports|{depth}`.

    Returns:
        "error" when the report's state header is ERROR; "findings" with
        one degraded Finding when it is BROKEN; else "ok".
    """
    binary = context.tool_environment.binary("lint-imports")
    if binary is None:
        return ActionResult(
            status="error", summary=context.unavailable_message("lint-imports")
        )

    report = run_lint_imports_check_impl(
        lint_imports_binary=str(binary),
        project_dir=str(context.project_dir),
        timeout_seconds=context.resolve_timeout("lint-imports"),
        python_executable=str(context.environment.interpreter),
    )
    header = next((line for line in report.splitlines() if line.strip()), "")
    if "ERROR" in header:
        return ActionResult(status="error", summary=report)
    if "BROKEN" in header:
        finding = Finding(key=f"lint-imports|{depth}", message=report)
        return ActionResult(
            status="findings",
            summary="lint-imports found contract violations.",
            findings=[finding],
            fix_text=report,
        )
    return ActionResult(status="ok", summary="lint-imports found no issues.")


def _run_tach(context: ToolContext, depth: str) -> ActionResult:
    """Run tach and map the outcome onto an ActionResult.

    `code_checker_tach.runners.run_tach_check` discards the subprocess
    return code, so this builds and runs the same command itself to read
    it, reusing that runner's own text formatting for the finding's
    message. tach's output has no stable per-location key, so a finding is
    reported once, keyed `tach|{depth}`.

    Returns:
        "error" if tach timed out or failed to run; "findings" with one
        degraded Finding on a non-zero exit; else "ok".
    """
    binary = context.tool_environment.binary("tach")
    if binary is None:
        return ActionResult(status="error", summary=context.unavailable_message("tach"))

    timeout_seconds = context.resolve_timeout("tach")
    result = execute_command(
        [str(binary), "check", "--output", "json"],
        cwd=str(context.project_dir),
        timeout_seconds=timeout_seconds,
    )
    if result.timed_out:
        return ActionResult(
            status="error",
            summary=f"tach check timed out after {timeout_seconds} seconds.",
        )
    if result.execution_error:
        return ActionResult(
            status="error",
            summary=f"tach check failed to run: {result.execution_error}",
        )

    output = result.stdout
    if result.stderr:
        output = output + "\n" + result.stderr if output else result.stderr
    stripped = output.strip()
    message = (
        f"tach check completed:\n{stripped}"
        if stripped
        else "tach check passed (no output)."
    )

    if result.return_code == 0:
        return ActionResult(status="ok", summary="tach found no issues.")

    finding = Finding(key=f"tach|{depth}", message=message)
    return ActionResult(
        status="findings",
        summary="tach found architecture boundary violations.",
        findings=[finding],
        fix_text=message,
    )


def _run_ruff(context: ToolContext, depth: str) -> ActionResult:
    """Run ruff check and map the outcome onto an ActionResult.

    `depth` is accepted but unused, so the signature matches every other
    `_CHECK_RUNNERS` entry.

    Returns:
        "error" if target directories cannot be resolved, ruff timed
        out/failed to run, or its JSON output could not be parsed;
        "findings" with one Finding per message; else "ok".
    """
    del depth
    project_dir = str(context.project_dir)
    dirs = resolve_target_directories(project_dir, None)
    if isinstance(dirs, str):
        return ActionResult(status="error", summary=dirs)

    binary = context.tool_environment.binary("ruff")
    if binary is None:
        return ActionResult(status="error", summary=context.unavailable_message("ruff"))

    timeout_seconds = context.resolve_timeout("ruff")
    result = execute_command(
        [str(binary), "check", "--output-format", "json", *dirs],
        cwd=project_dir,
        timeout_seconds=timeout_seconds,
    )
    if result.timed_out:
        return ActionResult(
            status="error",
            summary=f"ruff timed out after {timeout_seconds} seconds.",
        )
    if result.execution_error:
        return ActionResult(
            status="error", summary=f"ruff failed to run: {result.execution_error}"
        )

    messages, parse_error = parse_ruff_json_output(result.stdout, project_dir)
    if parse_error:
        return ActionResult(status="error", summary=parse_error)

    findings = [
        Finding(
            key=f"{message.filename}|{message.code}|{message.message}",
            message=message.message,
            path=message.filename,
            rule=message.code,
        )
        for message in messages
    ]
    return _result_from_findings(
        error=None,
        findings=findings,
        ok_summary="ruff found no issues.",
        findings_summary=f"ruff found {len(findings)} issue(s).",
    )


def _run_bandit(context: ToolContext, depth: str) -> ActionResult:
    """Run bandit and map the outcome onto an ActionResult.

    `depth` is accepted but unused, so the signature matches every other
    `_CHECK_RUNNERS` entry.

    Returns:
        "error" if target directories cannot be resolved or bandit itself
        errored; "findings" with one Finding per message; else "ok".
    """
    del depth
    project_dir = str(context.project_dir)
    dirs = resolve_target_directories(project_dir, None)
    if isinstance(dirs, str):
        return ActionResult(status="error", summary=dirs)

    binary = context.tool_environment.binary("bandit")
    if binary is None:
        return ActionResult(
            status="error", summary=context.unavailable_message("bandit")
        )

    result = run_bandit_check_impl(
        bandit_binary=str(binary),
        project_dir=project_dir,
        target_directories=dirs,
        timeout_seconds=context.resolve_timeout("bandit"),
    )
    findings = [
        Finding(
            key=f"{message.filename}|{message.test_id}|{message.issue_text}",
            message=message.issue_text,
            path=message.filename,
            rule=message.test_id,
            severity=message.issue_severity,
        )
        for message in result.messages
    ]
    return _result_from_findings(
        error=result.error,
        findings=findings,
        ok_summary="bandit found no issues.",
        findings_summary=f"bandit found {len(findings)} issue(s).",
    )


_CHECK_DEPTHS: dict[str, tuple[str, ...]] = {
    "quick": ("mypy",),
    "standard": ("mypy", "pylint"),
    "full": (
        "mypy",
        "pylint",
        "vulture",
        "lint-imports",
        "tach",
        "ruff",
        "bandit",
    ),
}

_CHECK_RUNNERS: dict[str, Callable[[ToolContext, str], ActionResult]] = {
    "mypy": _run_mypy,
    "pylint": _run_pylint,
    "vulture": _run_vulture,
    "lint-imports": _run_lint_imports,
    "tach": _run_tach,
    "ruff": _run_ruff,
    "bandit": _run_bandit,
}


def _run_check(context: ToolContext, depth: str) -> ActionResult:
    """Run the check tools declared for `depth` and merge their outcomes.

    Returns:
        "error" immediately if any tool declared for `depth` is
        unavailable, without running any of them; otherwise the
        worst-status-wins merge of each tool's ActionResult.
    """
    tools = _CHECK_DEPTHS[depth]
    for tool in tools:
        if not context.is_tool_available(tool):
            return ActionResult(
                status="error", summary=context.unavailable_message(tool)
            )
    results = [_CHECK_RUNNERS[tool](context, depth) for tool in tools]
    return _merge(results)


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

    def prompt_fragments(self) -> dict[str, str]:
        """Prompt text PythonToolkit contributes to mcp-coder's prompts.

        Returns:
            `language_context`, `check_instructions`, and `fix.check` — the
            Mypy Fix prompt, with its `[mypy_output]` placeholder dropped
            since the actual output now travels via `ActionResult.fix_text`.
        """
        return {
            "language_context": "This is a Python project.",
            "check_instructions": "Run pylint, mypy and pytest via the MCP tools.",
            "fix.check": _FIX_CHECK_PROMPT,
        }
