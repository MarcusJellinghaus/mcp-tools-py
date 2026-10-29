"""Classify a pytest run and render the shared verdict texts."""

from dataclasses import dataclass
from enum import Enum

from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary
from mcp_tools_py.code_checker_pytest.reporting import (
    FAILED_OUTCOMES,
    MAX_OUTPUT_LINES,
    OutputBuilder,
    get_test_summary,
)
from mcp_tools_py.code_checker_pytest.utils import get_pytest_exit_code_info

XDIST_MARKER = "Different tests were collected"
XDIST_HINT = (
    "Hint: pytest-xdist workers collected different tests. Parametrize values "
    "must be identical across workers (no `datetime.now()` or random values). "
    "Pass `-n 0` to disable xdist and run the tests anyway."
)
_ERROR_TAIL_LINES = 50


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
    if code != 0 and not (code == 2 and report and _has_collection_problems(report)):
        lines.append(f"Exit code {code}: {get_pytest_exit_code_info(code)[0]}")
    if verdict.problems:
        lines.append("Problems:")
        lines.append(cap_problems(verdict.problems) + _xdist_hint(verdict.problems))
    return "\n".join(lines)


def format_suspicious_text(collected: int) -> str:
    """Render the text for a SUSPICIOUS verdict.

    Args:
        collected: Number of collected tests

    Returns:
        The not-verified message.
    """
    return f"Collected {collected} tests but none reported an outcome. Not verified."


def format_collection_problems(report: PytestReport | None, verdict: RunVerdict) -> str:
    """Render what the failure prompt omits: collection errors and the xdist hint.

    Args:
        report: The parsed pytest report, if any
        verdict: The verdict to render

    Returns:
        The "Collection problems" block, or "" when there is nothing to add.
    """
    if not verdict.problems:
        return ""
    ctx = report.error_context if report else None
    body = (
        cap_problems(["\n".join(ctx.collection_errors)])
        if ctx and ctx.collection_errors
        else ""
    )
    hint = _xdist_hint(verdict.problems)
    return f"Collection problems:\n{body}{hint}".rstrip() if body or hint else ""


def cap_problems(problems: list[str]) -> str:
    """Join problems, capped at MAX_OUTPUT_LINES with a truncation marker.

    Args:
        problems: Problem texts

    Returns:
        The joined, capped text.
    """
    output = OutputBuilder(MAX_OUTPUT_LINES)
    for problem in problems:
        if not output.add(problem + "\n"):
            break
    return output.get_result()


def _merge_problems(report: PytestReport, with_tail: bool) -> list[str]:
    """Collect problems from collectors, collection errors and the output tail.

    Returns:
        De-duplicated problems, first occurrence kept.
    """
    ctx = report.error_context
    items = [
        c.longrepr
        for c in report.collectors or []
        if c.outcome in FAILED_OUTCOMES and c.longrepr
    ]
    if ctx and ctx.collection_errors:
        items.append("\n".join(ctx.collection_errors))
    # ErrorContext holds the full output on every non-zero exit, so the tail is only used for ERROR
    if with_tail and not items and ctx and ctx.error_message.strip():
        items.append("\n".join(ctx.error_message.splitlines()[-_ERROR_TAIL_LINES:]))
    seen: set[str] = set()
    problems = []
    for item in items:
        key = _dedup_key(item)
        if key not in seen:
            seen.add(key)
            problems.append(item)
    return problems


def _dedup_key(text: str) -> str:
    """Return the de-duplication key for a problem text."""
    if XDIST_MARKER in text:
        return XDIST_MARKER
    stripped = text.strip()
    return stripped.splitlines()[0] if stripped else ""


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
    """Return True when collectors failed or collection errors were recorded."""
    ctx = report.error_context
    failed_collectors = any(
        c.outcome in FAILED_OUTCOMES for c in report.collectors or []
    )
    return failed_collectors or bool(ctx and ctx.collection_errors)
