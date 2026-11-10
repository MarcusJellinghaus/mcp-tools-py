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
from mcp_tools_py.code_checker_tach.reporting import format_tach_report
from mcp_tools_py.code_checker_tach.runners import run_tach_check
from mcp_tools_py.code_checker_vulture.runners import run_vulture_check
from mcp_tools_py.utils.project_config import (
    resolve_source_directories,
    resolve_target_directories,
)
from mcp_tools_py.utils.report_budget import (
    TOOL_CHARS,
    TOOL_LINES,
    Location,
    bound_text,
    render_locations,
)
from mcp_tools_py.utils.report_counts import format_dir_split, plural
from mcp_tools_py.utils.ruff_parsing import parse_ruff_json_output
from mcp_tools_py.utils.subprocess_runner import execute_command
from mcp_tools_py.utils.tool_context import ToolContext

FIX_TEXT_HINT = "Fix these and rerun the check to see the rest."


def _location(
    finding: Finding, location: str | None, details: tuple[str, ...]
) -> tuple[Location, bool]:
    """Build the rendered `Location` of one finding.

    `location` is "path:line" or a whole test node id; without it the
    finding's path is used. A finding with neither shows its message alone.

    Returns:
        The Location, and whether it names a real path.
    """
    if location:
        path, sep, line = location.rpartition(":")
        if sep and path and line.isdigit():
            return Location(path, int(line), finding.message, details), True
        return Location(location, None, finding.message, details), True
    if finding.path:
        return Location(finding.path, None, finding.message, details), True
    return Location(finding.message, None, None, details), False


def _render_fix_text(
    findings: list[Finding],
    locations: list[str | None],
    details: list[tuple[str, ...]] | None = None,
) -> str:
    """Render findings grouped by rule, largest group first.

    `locations` and `details` (extra lines under a row) run parallel to
    `findings`.

    Returns:
        Per rule a header line with its count and directory split, then its
        rows from `render_locations`; unbounded.
    """
    groups: dict[str, list[tuple[Location, bool]]] = {}
    for i, (finding, location) in enumerate(zip(findings, locations)):
        item = _location(finding, location, details[i] if details else ())
        groups.setdefault(finding.rule or "", []).append(item)
    lines: list[str] = []
    for rule, items in sorted(groups.items(), key=lambda group: -len(group[1])):
        count = plural(len(items), "finding")
        header = f"{rule} ({count})" if rule else count
        paths = [item.path for item, has_path in items if has_path]
        if paths:
            header += f" {format_dir_split(paths)}"
        lines.append(header)
        lines.extend(render_locations([item for item, _ in items], FIX_TEXT_HINT))
    return "\n".join(lines)


def _result_from_findings(
    error: str | None,
    findings: list[Finding],
    ok_summary: str,
    findings_summary: str,
    locations: list[str | None] | None = None,
) -> ActionResult:
    """Map a tool's error/findings outcome onto ActionResult's status rules.

    `locations`, when given, runs parallel to `findings`: "path:line" or a
    test node id replacing the finding's path.

    Returns:
        status="error" when `error` is set; "findings" (with `fix_text`
        rendered by rule and bounded at TOOL_LINES/TOOL_CHARS) when findings
        is non-empty; otherwise "ok".
    """
    if error is not None:
        return ActionResult(status="error", summary=error, findings=findings)
    if findings:
        locs = locations or [None] * len(findings)
        fix_text = bound_text(_render_fix_text(findings, locs), hint=FIX_TEXT_HINT)
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
        concatenated. fix_text joins each result's own fix_text, rendered
        from that result's findings when not set; empty parts are skipped.
        Each part gets an even share of the TOOL_LINES/TOOL_CHARS budget.
    """
    worst = max(results, key=lambda result: _STATUS_RANK[result.status])
    findings = [finding for result in results for finding in result.findings]
    summary = "; ".join(result.summary for result in results)
    raw = "\n\n".join(result.raw for result in results if result.raw)
    parts = [
        result.fix_text
        or _render_fix_text(result.findings, [None] * len(result.findings))
        for result in results
    ]
    parts = [part for part in parts if part]
    share = max(len(parts), 1)
    fix_text = bound_text(
        "\n".join(
            bound_text(part, TOOL_LINES // share, TOOL_CHARS // share, FIX_TEXT_HINT)
            for part in parts
        ),
        hint=FIX_TEXT_HINT,
    )
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
    fix_text = bound_text(
        _render_fix_text(
            findings,
            [f"{m.file}:{m.line}" if m.line >= 0 else None for m in issues],
            details=[tuple(format_hint_lines(m.hint)) for m in issues],
        ),
        hint=FIX_TEXT_HINT,
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

    `depth` is accepted but unused, so the signature matches every other
    `_CHECK_RUNNERS` entry. Finding keys are line-insensitive:
    `vulture|<file>|<kind>|<name-or-message>`.

    Returns:
        "error" if target directories cannot be resolved, vulture timed
        out/failed to run, or its output parsed to no messages but had
        other lines; "findings" with one Finding per message; else "ok".
    """
    del depth
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

    result = run_vulture_check(
        vulture_binary=str(binary),
        project_dir=str(project_dir),
        target_directories=dirs,
        whitelist_path=whitelist,
        timeout_seconds=context.resolve_timeout("vulture"),
    )
    if result.error is not None:
        return ActionResult(status="error", summary=result.error)
    if not result.messages and result.unparsed:
        raw = "\n".join(result.unparsed)
        return ActionResult(
            status="error", summary=_one_line(bound_text(raw, max_lines=5))
        )

    findings = [
        Finding(
            key=(
                f"vulture|{message.file}|{message.kind}|"
                f"{message.name or message.message}"
            ),
            message=message.message,
            path=message.file,
            rule=message.kind,
        )
        for message in result.messages
    ]
    return _result_from_findings(
        None,
        findings,
        "vulture found no issues.",
        f"vulture found {len(findings)} issue(s).",
        locations=[f"{message.file}:{message.line}" for message in result.messages],
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

    Error diagnostics become findings keyed
    `tach|<kind>|<file>|<usage_module>|<dependency>`, so diagnostics with no
    module pair still differ by kind; warnings are named in the
    summary only. Output that is not tach's JSON has no stable key, so on a
    non-zero exit it is reported once, keyed `tach|{depth}`.

    Returns:
        "error" if tach timed out or failed to run; "findings" with one
        Finding per error diagnostic, or one degraded Finding when a failed
        run's output could not be parsed; else "ok".
    """
    binary = context.tool_environment.binary("tach")
    if binary is None:
        return ActionResult(status="error", summary=context.unavailable_message("tach"))

    result = run_tach_check(
        tach_binary=str(binary),
        project_dir=str(context.project_dir),
        timeout_seconds=context.resolve_timeout("tach"),
    )
    if result.error is not None:
        return ActionResult(status="error", summary=result.error)
    if result.raw is not None and result.return_code == 0:
        unparsed = _one_line(bound_text(result.raw, max_lines=5))
        return ActionResult(
            status="ok", summary=f"tach check passed; unparsed output: {unparsed}"
        )
    if result.raw is not None or (result.return_code and not result.diagnostics):
        report = format_tach_report(result)
        finding = Finding(key=f"tach|{depth}", message=report)
        return ActionResult(
            status="findings",
            summary="tach found architecture boundary violations.",
            findings=[finding],
            fix_text=report,
        )

    errors = [d for d in result.diagnostics if d.severity == "error"]
    warnings = [d.message for d in result.diagnostics if d.severity != "error"]
    suffix = ""
    if warnings:
        suffix = f"; tach: {len(warnings)} warning(s): {', '.join(warnings[:3])}"
    findings = [
        Finding(
            key=f"tach|{d.kind}|{d.file}|{d.usage_module}|{d.dependency}",
            message=d.message,
            path=d.file,
            rule=d.kind,
            severity=d.severity,
        )
        for d in errors
    ]
    return _result_from_findings(
        None,
        findings,
        f"tach found no issues.{suffix}",
        f"tach found {len(findings)} issue(s).{suffix}",
        locations=[f"{d.file}:{d.line}" if d.file else None for d in errors],
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


# mypy has no cache on a fresh checkout.
_LONG_CHECK_TIMEOUT = 600  # seconds; mypy and pylint at every check depth
_LONG_CHECK_TOOLS = frozenset({"mypy", "pylint"})


def _run_check(context: ToolContext, depth: str) -> ActionResult:
    """Run the check tools declared for `depth` and merge their outcomes.

    mypy and pylint default to a 600 s timeout; the other tools keep the
    usual default. `[tool.mcp-tools-py]` `<tool>-timeout` and
    `check-timeout` still win over both.

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
    long_context = replace(context, check_timeout=_LONG_CHECK_TIMEOUT)
    results = [
        _CHECK_RUNNERS[tool](
            long_context if tool in _LONG_CHECK_TOOLS else context, depth
        )
        for tool in tools
    ]
    return _merge(results)
