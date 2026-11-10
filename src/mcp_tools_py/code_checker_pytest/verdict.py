"""Classify a pytest run and render the shared verdict texts."""

from dataclasses import dataclass
from enum import Enum

from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary
from mcp_tools_py.code_checker_pytest.reporting import (
    XDIST_MARKER,
    collected_test_ids,
    collectors_failed_line,
    failed_collector_count,
    get_test_summary,
    group_failed_collectors,
    plural,
    selected_count,
)
from mcp_tools_py.code_checker_pytest.utils import get_pytest_exit_code_info
from mcp_tools_py.utils.report_budget import ERROR_TAIL_LINES, TOOL_LINES, bound_text

XDIST_HINT = (
    "Hint: pytest-xdist workers collected different tests. Parametrize values "
    "must be identical across workers (no `datetime.now()` or random values). "
    "Pass `-n 0` to disable xdist and run the tests anyway."
)
COLLECT_HINT = "Narrow the selection (a path or -k in extra_args) to list fewer tests."
PROBLEMS_HINT = (
    "Narrow the selection (a path or -k in extra_args) and rerun to see the rest."
)


class RunStatus(str, Enum):
    """Overall outcome of a pytest run."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SUSPICIOUS = "suspicious"


@dataclass(frozen=True)
class RunVerdict:
    """The single decision about what a pytest run means."""

    status: RunStatus
    problems: list[str]
    exit_code: int


def classify_run(report: PytestReport) -> RunVerdict:
    """Decide the status of a pytest run; the first matching rule wins.

    Args:
        report: The parsed pytest report

    Returns:
        The verdict with status, merged problems and exit code.
    """
    summary, ctx = report.summary, report.error_context
    exit_code = ctx.exit_code if ctx else 0
    if (summary.failed or 0) > 0 or (summary.error or 0) > 0:
        status = RunStatus.FAILED
    elif exit_code != 0:
        status = RunStatus.ERROR
    elif summary.collected > 0 and not _has_outcomes(summary):
        status = RunStatus.SUSPICIOUS
    else:
        status = RunStatus.PASSED
    problems = _merge_problems(report, with_tail=status is RunStatus.ERROR)
    return RunVerdict(status, problems, exit_code)


def format_error_text(report: PytestReport | None, verdict: RunVerdict) -> str:
    """Render the text for an ERROR (or unknown) verdict.

    Args:
        report: The parsed pytest report, if any
        verdict: The verdict to render

    Returns:
        Headline, counts, exit-code line and capped problems.
    """
    lines = ["Pytest run reported an error."]
    if report and _has_outcomes(report.summary):
        lines.append(get_test_summary(report))
    else:
        lines.append("Pytest run did not complete.")
    code = verdict.exit_code
    if code != 0 and not (report and _collection_explains_exit(report)):
        lines.append(f"Exit code {code}: {get_pytest_exit_code_info(code)[0]}")
    if verdict.problems:
        lines.append("Problems:")
        count_line = collectors_failed_line(report) if report else ""
        if count_line:
            lines.extend([count_line, ""])
        lines.append(cap_problems(verdict.problems) + _xdist_hint(verdict.problems))
    return "\n".join(lines)


def format_suspicious_text(collected: int, deselected: int | None = None) -> str:
    """Render the text for a SUSPICIOUS verdict.

    Args:
        collected: Number of collected tests
        deselected: Number of deselected tests, subtracted from ``collected``

    Returns:
        The not-verified message.
    """
    selected = collected - (deselected or 0)
    return f"Collected {selected} tests but none reported an outcome. Not verified."


def format_collect_only_text(report: PytestReport) -> str:
    """Render the text for a ``--collect-only`` run.

    Args:
        report: The parsed pytest report

    Returns:
        The selected count, then one test ID per line, bounded at TOOL_LINES
        and ending with COLLECT_HINT when cut.
    """
    selected = selected_count(report.summary)
    deselected = report.summary.deselected or 0
    header = f"Collected {selected} {plural(selected, 'test')}"
    if deselected:
        header += f" ({deselected} deselected)"
    text = f"{header} in {report.duration:.2f} seconds. No tests were run.\n"
    ids = collected_test_ids(report)
    if ids:
        text += "\n".join(ids) + "\n"
    return bound_text(text, TOOL_LINES, hint=COLLECT_HINT)


def format_collection_problems(verdict: RunVerdict) -> str:
    """Render what the failure prompt omits: the xdist hint.

    Args:
        verdict: The verdict to render

    Returns:
        The "Collection problems" block, or "" when there is nothing to add.
    """
    hint = _xdist_hint(verdict.problems)
    return f"Collection problems:{hint}" if hint else ""


def cap_problems(problems: list[str]) -> str:
    """Join problems, bounded at TOOL_LINES.

    Args:
        problems: Problem texts

    Returns:
        The joined, bounded text, ending with PROBLEMS_HINT when cut.
    """
    return bound_text("\n".join(problems), hint=PROBLEMS_HINT)


def _merge_problems(report: PytestReport, with_tail: bool) -> list[str]:
    """Collect problems from collectors and the output tail.

    Returns:
        One text per distinct collector error, or the output tail when there are none.
    """
    ctx = report.error_context
    items = group_failed_collectors(report)
    # ErrorContext holds the full output on every non-zero exit, so the tail is only used for ERROR
    if with_tail and not items and ctx and ctx.error_message.strip():
        items.append("\n".join(ctx.error_message.splitlines()[-ERROR_TAIL_LINES:]))
    return items


def _xdist_hint(problems: list[str]) -> str:
    """Return the xdist hint when any problem mentions the xdist marker."""
    return "\n" + XDIST_HINT if any(XDIST_MARKER in p for p in problems) else ""


def _has_outcomes(summary: Summary) -> bool:
    """Return True when any test reported an outcome."""
    counts = (
        summary.passed,
        summary.failed,
        summary.error,
        summary.skipped,
        summary.xfailed,
        summary.xpassed,
    )
    return any((count or 0) > 0 for count in counts)


def _has_collection_problems(report: PytestReport) -> bool:
    """Return True when collectors failed."""
    return failed_collector_count(report) > 0


def _collection_explains_exit(report: PytestReport) -> bool:
    """Return True when collectors failed and no test failed or errored."""
    summary = report.summary
    return (
        _has_collection_problems(report)
        and (summary.failed or 0) + (summary.error or 0) == 0
    )
