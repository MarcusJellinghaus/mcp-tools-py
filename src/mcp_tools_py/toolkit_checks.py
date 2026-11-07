"""Check-tool runner implementations used by PythonToolkit's check action."""

from collections.abc import Callable
from dataclasses import replace

from mcp_coder_utils.toolkit import ActionResult, Finding

from mcp_tools_py.code_checker_bandit.runners import run_bandit_check_impl
from mcp_tools_py.code_checker_deptry.runners import run_deptry_check_impl
from mcp_tools_py.code_checker_lint_imports.runners import run_lint_imports_check_impl
from mcp_tools_py.code_checker_mypy.reporting import format_hint_lines, run_signals
from mcp_tools_py.code_checker_mypy.runners import MYPY_EXIT_PREFIX, run_mypy_check
from mcp_tools_py.code_checker_pylint.runners import get_pylint_results
from mcp_tools_py.code_checker_tach.runners import format_tach_result
from mcp_tools_py.code_checker_vulture.runners import run_vulture_check
from mcp_tools_py.utils.project_config import (
    resolve_source_directories,
    resolve_target_directories,
)
from mcp_tools_py.utils.ruff_parsing import parse_ruff_json_output
from mcp_tools_py.utils.subprocess_runner import execute_command
from mcp_tools_py.utils.tool_context import ToolContext


def _finding_line(finding: Finding, location: str | None = None) -> str:
    """One bullet line for `finding`, used to build `ActionResult.fix_text`.

    `location` (e.g. "path:line" or a test node id) replaces `finding.path`
    when given.

    Returns:
        "- location: rule: message", omitting location/rule when absent.
    """
    where = location or finding.path
    prefix = ": ".join(part for part in (where, finding.rule) if part)
    return f"- {prefix}: {finding.message}" if prefix else f"- {finding.message}"


def _result_from_findings(
    error: str | None,
    findings: list[Finding],
    ok_summary: str,
    findings_summary: str,
    locations: list[str | None] | None = None,
) -> ActionResult:
    """Map a tool's error/findings outcome onto ActionResult's status rules.

    `locations`, when given, runs parallel to `findings` and is passed to
    `_finding_line` for each one.

    Returns:
        status="error" when `error` is set; "findings" (with `fix_text`
        built from `findings`, one bullet line each) when findings is
        non-empty; otherwise "ok".
    """
    if error is not None:
        return ActionResult(status="error", summary=error, findings=findings)
    if findings:
        locs = locations or [None] * len(findings)
        fix_text = "\n".join(
            _finding_line(finding, location)
            for finding, location in zip(findings, locs)
        )
        return ActionResult(
            status="findings",
            summary=findings_summary,
            findings=findings,
            fix_text=fix_text,
        )
    return ActionResult(status="ok", summary=ok_summary)


_STATUS_RANK: dict[str, int] = {"skipped": 0, "ok": 1, "findings": 2, "error": 3}


def _merge(results: list[ActionResult]) -> ActionResult:
    """Combine check results with worst-status-wins semantics.

    Returns:
        One ActionResult: status is the worst across `results` ("error" >
        "findings" > "ok" > "skipped"), findings and non-empty raw outputs
        concatenated. fix_text joins each result's own fix_text, rebuilt from
        that result's findings when not set; empty parts are skipped.
    """
    worst = max(results, key=lambda result: _STATUS_RANK[result.status])
    findings = [finding for result in results for finding in result.findings]
    summary = "; ".join(result.summary for result in results)
    raw = "\n\n".join(result.raw for result in results if result.raw)
    parts = [
        result.fix_text
        or "\n".join(_finding_line(finding) for finding in result.findings)
        for result in results
    ]
    fix_text = "\n".join(part for part in parts if part)
    return ActionResult(
        status=worst.status,
        summary=summary,
        findings=findings,
        raw=raw,
        fix_text=fix_text,
    )


def _one_line(text: str) -> str:
    """Collapse `text` onto one line, for use in `ActionResult.summary`.

    Returns:
        `text` with every run of whitespace replaced by a single space.
    """
    return " ".join(text.split())


def _run_mypy(context: ToolContext, depth: str) -> ActionResult:
    """Run mypy and map the outcome onto an ActionResult.

    `depth` is accepted but unused, so the signature matches every other
    `_CHECK_RUNNERS` entry.

    Returns:
        "error" if target directories cannot be resolved or mypy itself
        errored; "findings" with one Finding per error message; else "ok".
        The summary carries the run's signals on one line, fix_text the
        message hints and raw mypy's raw output, empty when the runner
        returned early (e.g. on a timeout).
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
    issues = [message for message in result.messages if message.severity == "error"]
    findings = [
        Finding(
            key=f"{message.file}|{message.code}|{message.message}",
            message=message.message,
            path=message.file,
            rule=message.code,
            severity=message.severity,
        )
        for message in issues
    ]
    fix_text = "\n".join(
        line
        for message, finding in zip(issues, findings)
        for line in [
            _finding_line(
                finding,
                f"{message.file}:{message.line}" if message.line >= 0 else None,
            ),
            *format_hint_lines(message.hint),
        ]
    )
    suffix = "".join(f" {_one_line(signal)}" for signal in run_signals(result))
    error = result.error
    if error and error.startswith(MYPY_EXIT_PREFIX):
        error = _one_line(error)
    action = _result_from_findings(
        error=error,
        findings=findings,
        ok_summary=f"mypy found no issues.{suffix}",
        findings_summary=f"mypy found {len(findings)} issue(s).{suffix}",
    )
    return replace(action, fix_text=fix_text, raw=result.raw_output or "")


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
        locations=[f"{message.path}:{message.line}" for message in result.messages],
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

    `code_checker_tach.runners.run_tach_check` returns only text, so this
    builds and runs the same command itself to read the return code, and
    shares that runner's `format_tach_result` for the finding's message.
    tach's output has no stable per-location key, so a finding is reported
    once, keyed `tach|{depth}`.

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

    if result.return_code == 0:
        return ActionResult(status="ok", summary="tach found no issues.")

    message = format_tach_result(result)
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
        locations=[f"{message.filename}:{message.line}" for message in messages],
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
        locations=[
            f"{message.filename}:{message.line_number}" for message in result.messages
        ],
    )


def _run_deptry(context: ToolContext, depth: str) -> ActionResult:
    """Run deptry and map the outcome onto an ActionResult.

    `depth` is accepted but unused, so the signature matches every other
    `_CHECK_RUNNERS` entry. Targets exclude test paths, so test-only imports
    are not reported as DEP004.

    Returns:
        "error" if source directories cannot be resolved or deptry itself
        errored; "findings" with one Finding per message; else "ok".
    """
    del depth
    project_dir = str(context.project_dir)
    dirs = resolve_source_directories(project_dir, None)
    if isinstance(dirs, str):
        return ActionResult(status="error", summary=dirs)

    result = run_deptry_check_impl(
        str(context.environment.interpreter),
        project_dir,
        dirs,
        timeout_seconds=context.resolve_timeout("deptry"),
    )
    findings = [
        Finding(
            key=f"{message.file}|{message.code}|{message.module}",
            message=message.message,
            path=message.file,
            rule=message.code,
        )
        for message in result.messages
    ]
    return _result_from_findings(
        error=result.error,
        findings=findings,
        ok_summary="deptry found no issues.",
        findings_summary=f"deptry found {len(findings)} issue(s).",
        locations=[
            f"{message.file}:{message.line}" if message.line is not None else None
            for message in result.messages
        ],
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
        "deptry",
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
    "deptry": _run_deptry,
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
