"""Functions for formatting and reporting pytest test results."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    PytestReport,
    StageInfo,
    Summary,
    Test,
    TracebackEntry,
)
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.report_budget import (
    FAILED_IDS,
    MAX_COLLECTOR_IDS,
)
from mcp_tools_py.utils.report_budget import MAX_FAILURES as MAX_FAILURES
from mcp_tools_py.utils.report_budget import TOOL_CHARS, TOOL_LINES, bound_text

logger = logging.getLogger(__name__)
# Constants to avoid magic numbers
FAILED_OUTCOMES = ["failed", "error"]
PYTEST_HINT = "Use extra_args=['<nodeid>', '-vv'] to see one test in full."
SHOW_OUTPUT_HINT = "Use extra_args=['<nodeid>', '-s'] to see one test's output."
CLOSING_QUESTION = (
    "Can you provide an explanation for why these tests failed"
    " and suggest how they could be fixed?"
)
TESTS_HEADER = "The following tests failed during the test session:"
SEPARATOR = "=" * 79
MIN_TEST_LINES = 6
FENCE = "```"
NO_CAPTURED_OUTPUT_NOTE = "Note: no passing test produced captured output."
XDIST_MARKER = "Different tests were collected"


def should_show_details(_test_results: Dict[str, Any], show_details: bool) -> bool:
    """Determine if detailed output should be shown based on test results and user preference.

    Args:
        _test_results: Dictionary containing test summary information (currently unused)
        show_details: User preference for showing details

    Returns:
        True if conditions meet criteria for showing details, False otherwise
    """
    # If show_details is False, never show details (explicit user choice)
    if not show_details:
        return False

    # If show_details is True, always show details (but output will be limited by other mechanisms)
    # The limitation of max failures and output length is handled in create_prompt_for_failed_tests
    return True


def _get_failed_collectors(test_session_result: PytestReport) -> List[Collector]:
    """Extract failed collectors from test session result.

    Returns:
        Collectors whose outcome is failed or error.
    """
    if not test_session_result.collectors:
        return []

    return [
        collector
        for collector in test_session_result.collectors
        if collector.outcome in FAILED_OUTCOMES
    ]


def plural(count: int, noun: str) -> str:
    """Return `noun`, with an "s" unless `count` is 1."""
    return noun if count == 1 else f"{noun}s"


def _e_lines(longrepr: str) -> list[str]:
    """Return the `E   ` lines of a longrepr."""
    return [line for line in longrepr.splitlines() if line.startswith("E   ")]


def _collector_key(longrepr: str) -> str:
    """Return the key that decides which collector errors share a cause.

    Returns:
        The xdist marker if present, else all `E   ` lines joined, else the
        last non-empty line, or "" when there is none.
    """
    if XDIST_MARKER in longrepr:
        return XDIST_MARKER
    e_lines = _e_lines(longrepr)
    if e_lines:
        return "\n".join(e_lines)
    non_empty = [line for line in longrepr.splitlines() if line.strip()]
    return non_empty[-1] if non_empty else ""


def _render_collector_group(longrepr: str, node_ids: list[str]) -> str:
    """Render one distinct collector error with the other collectors it hit.

    Args:
        longrepr: The first longrepr seen for this error
        node_ids: Unique node IDs with this error, first occurrence first

    Returns:
        The `E   ` lines as a headline if any, the longrepr, and a "same error"
        line if more than one collector is affected.
    """
    e_lines = _e_lines(longrepr)
    parts = ["\n".join(e_lines), longrepr] if e_lines else [longrepr]
    others = node_ids[1:]
    if others:
        listed = ", ".join(others[:MAX_COLLECTOR_IDS])
        hidden = len(others) - MAX_COLLECTOR_IDS
        if hidden > 0:
            listed += f", … and {hidden} more"
        noun = plural(len(others), "collector")
        parts.append(f"same error in {len(others)} more {noun}: {listed}")
    return "\n".join(parts)


def failed_collector_count(report: PytestReport) -> int:
    """Count the failed collectors, with or without a longrepr.

    Returns:
        The number of distinct node IDs among the failed collectors.
    """
    return len({collector.nodeid for collector in _get_failed_collectors(report)})


def group_failed_collectors(report: PytestReport) -> list[str]:
    """Group the failed collectors that have a longrepr by cause.

    Args:
        report: The parsed pytest report

    Returns:
        One rendered text per distinct error, in order of first occurrence.
    """
    groups: dict[str, tuple[str, list[str]]] = {}
    for collector in _get_failed_collectors(report):
        if not collector.longrepr:
            continue
        key = _collector_key(collector.longrepr)
        _, node_ids = groups.setdefault(key, (collector.longrepr, []))
        if collector.nodeid not in node_ids:
            node_ids.append(collector.nodeid)
    return [
        _render_collector_group(longrepr, node_ids)
        for longrepr, node_ids in groups.values()
    ]


def collectors_failed_line(report: PytestReport) -> str:
    """Render the count of failed collectors and distinct errors.

    Args:
        report: The parsed pytest report

    Returns:
        The count line, without the distinct errors when no collector has a
        longrepr to group by, or "" when no collector failed.
    """
    count = failed_collector_count(report)
    if not count:
        return ""
    line = f"{count} {plural(count, 'collector')} failed"
    distinct = len(group_failed_collectors(report))
    if not distinct:
        return line
    return f"{line} ({distinct} distinct {plural(distinct, 'error')})"


def _get_failed_tests(test_session_result: PytestReport) -> List[Test]:
    """Return every failed or errored test, in report order."""
    return [
        test
        for test in test_session_result.tests or []
        if test.outcome in FAILED_OUTCOMES
    ]


def _line_count(text: str) -> int:
    return len(text.splitlines())


def _fenced(label: str, text: str, max_lines: int, max_chars: int) -> str:
    """Render `text` as a fenced section, keeping its tail within the budget.

    The fences sit outside the bounded body, so they are always closed.

    Returns:
        The label line followed by the fenced body.
    """
    body_chars = max(0, max_chars - len(label) - 16)
    body = bound_text(text.rstrip("\n"), max_lines - 3, body_chars, keep="tail")
    return f"  {label}:\n{FENCE}\n{body}\n{FENCE}"


def _traceback(label: str, entries: List[TracebackEntry]) -> str:
    rows = [f"   - {entry.path}:{entry.lineno} - {entry.message}" for entry in entries]
    return "\n".join([f"  {label}:"] + rows)


class _Sections:
    """Sections kept in order while they fit in what is left of a budget."""

    def __init__(self, max_lines: int, max_chars: int) -> None:
        self.parts: List[str] = []
        self.lines = max_lines
        self.chars = max_chars

    def add(self, text: str) -> None:
        """Append `text` if it fits; otherwise skip it."""
        lines, chars = _line_count(text), len(text) + 1
        if lines <= self.lines and chars <= self.chars:
            self.parts.append(text)
            self.lines -= lines
            self.chars -= chars

    def bounded(self, text: str, share: int = 1) -> None:
        """Append `text` bounded to 1/`share` of the budget left."""
        self.add(
            bound_text(
                text, max(1, self.lines // share), max(0, self.chars // share - 1)
            )
        )

    def fenced(self, label: str, text: Optional[str]) -> None:
        """Append `text` as a tail-kept fenced section, if there is any."""
        if text:
            self.add(_fenced(label, text, self.lines, self.chars - 1))


def _render_setup(out: _Sections, setup: StageInfo, include_print_output: bool) -> None:
    out.add(f"  Test Setup Outcome: {setup.outcome}")
    if setup.crash:
        out.bounded(
            f"  Test Setup Crash Error Message: {setup.crash.message}\n"
            f"  Test Setup Crash Error Path: {setup.crash.path}\n"
            f"  Setup Crash Error Line: {setup.crash.lineno}",
            share=3,
        )
    if setup.longrepr:
        out.fenced("Test Setup Longrepr", setup.longrepr)
    elif setup.traceback:
        out.bounded(_traceback("Test Setup Traceback", setup.traceback))
    if include_print_output:
        out.fenced("Test Setup Stderr", setup.stderr)
        out.fenced("Test Setup Stdout", setup.stdout)


def _render_test(
    test: Test, include_print_output: bool, max_lines: int, max_chars: int
) -> str:
    """Render one failed test; each section takes from the budget left over.

    Order: header and message, longrepr (else traceback), stderr, stdout,
    then setup info when setup failed. A section that does not fit is skipped.

    Returns:
        The rendered test, or "" when not even the header fits.
    """
    out = _Sections(max_lines, max_chars)
    out.add(f"Test ID: {test.nodeid} - outcome {test.outcome}")
    if not out.parts:
        return ""
    call = test.call
    if call:
        if call.crash:
            out.bounded(f"  Error Message: {call.crash.message}", share=3)
        if call.longrepr:
            out.fenced("Longrepr", call.longrepr)
        elif call.traceback:
            out.bounded(_traceback("Traceback", call.traceback))
        if include_print_output:
            out.fenced("Stderr", call.stderr)
            out.fenced("Stdout", call.stdout)
    if test.setup and test.setup.outcome == "failed":
        _render_setup(out, test.setup, include_print_output)
    return "\n".join(out.parts)


def _collector_part(report: PytestReport, max_lines: int, max_chars: int) -> str:
    """Render the count line and one group per distinct collector error.

    Returns:
        The bounded collector text, or "" when no collector failed.
    """
    line = collectors_failed_line(report)
    if not line:
        return ""
    return bound_text(
        "\n\n".join([line] + group_failed_collectors(report)), max_lines, max_chars
    )


def _undetailed(tests: List[Test]) -> str:
    lines = [f"Failed tests without details ({len(tests)}):"]
    lines += [f"- {test.nodeid}" for test in tests[:FAILED_IDS]]
    hidden = len(tests) - FAILED_IDS
    if hidden > 0:
        lines.append(f"... and {hidden} more")
    return "\n".join(lines)


def _render_tests(
    candidates: List[Test], include_print_output: bool, max_lines: int, max_chars: int
) -> List[str]:
    """Render the candidates in order, each with an even share of what is left.

    Returns:
        One block per rendered test; stops at the first test whose share is
        too small.
    """
    separator_chars = len(SEPARATOR) + 4
    blocks: List[str] = []
    for index, test in enumerate(candidates):
        remaining = len(candidates) - index
        lines = max_lines // remaining
        if lines < MIN_TEST_LINES:
            break
        chars = max_chars // remaining - separator_chars
        block = _render_test(test, include_print_output, lines - 3, chars)
        if not block:
            break
        blocks.append(block)
        max_lines -= _line_count(block) + 3
        max_chars -= len(block) + separator_chars
    return blocks


@log_function_call
def create_prompt_for_failed_tests(
    test_session_result: PytestReport,
    include_print_output: bool = True,
    max_failures: int = MAX_FAILURES,
    max_lines: int = TOOL_LINES,
    max_chars: int = TOOL_CHARS,
) -> Optional[str]:
    """Creates a prompt for an LLM based on the failed tests from a test session result.

    Failed collectors come first. Up to `max_failures` tests then get an even
    share of the budget left; a reserved list names every failed test that got
    no detail. The prompt ends with the closing question and PYTEST_HINT.

    Args:
        test_session_result: The test session result to analyze
        include_print_output: Whether to include stdout/stderr output
        max_failures: Maximum number of tests rendered in detail
        max_lines: Line budget of the whole prompt
        max_chars: Character budget of the whole prompt

    Returns:
        A prompt string, or None if no tests failed
    """
    failed = _get_failed_tests(test_session_result)
    collectors = _collector_part(test_session_result, max_lines // 3, max_chars // 3)
    if not failed and not collectors:
        return None

    closing = f"{CLOSING_QUESTION}\n{PYTEST_HINT}"
    reserved = _undetailed(failed) if len(failed) > 1 else ""
    reserve = min(len(failed), FAILED_IDS) + 3 if reserved else 0
    collector_lines = _line_count(collectors) + 1 if collectors else 0
    lines_left = max_lines - collector_lines - reserve - 4
    chars_left = max_chars - sum(
        len(part) + 2 for part in (collectors, TESTS_HEADER, reserved, closing)
    )
    blocks = _render_tests(
        failed[:max_failures], include_print_output, lines_left, chars_left
    )

    sections = [collectors] if collectors else []
    if blocks:
        sections.append(TESTS_HEADER + "\n" + f"\n\n{SEPARATOR}\n\n".join(blocks))
    undetailed = failed[len(blocks) :]
    if undetailed:
        sections.append(_undetailed(undetailed))
    sections.append(closing)
    return "\n\n".join(sections)


@log_function_call
def create_prompt_for_passing_output(
    report: PytestReport, max_lines: int = TOOL_LINES
) -> str:
    """List the captured stdout and stderr of tests that did not fail.

    Covers the setup, call and teardown stages. Longrepr is never shown.

    Args:
        report: The test session result to read output from
        max_lines: Line budget; a cut ends with SHOW_OUTPUT_HINT

    Returns:
        The captured output per test, or NO_CAPTURED_OUTPUT_NOTE if no test printed
    """
    parts: List[str] = []
    for test in report.tests or []:
        if test.outcome in FAILED_OUTCOMES:
            continue
        stages = [
            (name, stage)
            for name, stage in (
                ("Setup", test.setup),
                ("Call", test.call),
                ("Teardown", test.teardown),
            )
            if stage
        ]
        blocks = [
            (f"{name} {kind}", text)
            for name, stage in stages
            for kind, text in (("stdout", stage.stdout), ("stderr", stage.stderr))
            if text
        ]
        if not blocks:
            continue
        parts.append(f"Test ID: {test.nodeid} - outcome {test.outcome}\n")
        parts.extend(
            f"  {label}:\n{FENCE}\n{text}\n{FENCE}\n" for label, text in blocks
        )

    if not parts:
        return NO_CAPTURED_OUTPUT_NOTE
    output = "Captured output of passing tests:\n" + "".join(parts)
    return bound_text(output, max_lines, hint=SHOW_OUTPUT_HINT)


def get_detailed_test_summary(
    test_session_result: PytestReport, show_details: bool
) -> str:
    """Enhanced summary that can include additional detail hints.

    Args:
        test_session_result: The test session result to summarize
        show_details: Whether to include hints about detail availability

    Returns:
        A string with the enhanced test summary
    """
    summary_base = get_test_summary(test_session_result)

    if show_details:
        test_results = {
            "summary": {
                "collected": test_session_result.summary.collected,
                "failed": test_session_result.summary.failed,
                "error": test_session_result.summary.error,
            }
        }
        if should_show_details(test_results, show_details):
            summary_base += " [Details available with show_details=True]"

    return summary_base


def selected_count(summary: Summary) -> int:
    """Return the tests left after deselection; an absent count means zero."""
    return summary.collected - (summary.deselected or 0)


def collected_test_ids(report: PytestReport) -> List[str]:
    """List the selected test IDs from the collectors, in collection order.

    Items that are themselves collectors (modules, classes) and deselected
    items are dropped. Item types are not filtered, so coroutines and
    doctests are kept.

    Returns:
        The test node IDs, or [] when the report has no collectors.
    """
    collectors = report.collectors or []
    collector_ids = {collector.nodeid for collector in collectors}
    return [
        item.nodeid
        for collector in collectors
        for item in collector.result
        if item.nodeid not in collector_ids and not item.deselected
    ]


def did_not_run_line(report: PytestReport) -> str:
    """Render how many selected tests did not run.

    Returns:
        A line such as "N of M selected tests did not run", or an empty
        string when every selected test ran.
    """
    selected = selected_count(report.summary)
    missing = selected - report.summary.total
    if missing <= 0:
        return ""
    return f"{missing} of {selected} selected tests did not run"


def get_test_summary(test_session_result: PytestReport) -> str:
    """Generate a human-readable summary of the test results.

    Args:
        test_session_result: The test session result to summarize

    Returns:
        A string with the test summary
    """
    summary = test_session_result.summary

    deselected = summary.deselected or 0
    header = f"Collected {selected_count(summary)} tests"
    if deselected > 0:
        header += f" ({deselected} deselected)"
    header += f" in {test_session_result.duration:.2f} seconds"

    parts = [header]

    if summary.passed is not None and summary.passed > 0:
        parts.append(f"✅ Passed: {summary.passed}")
    if summary.failed is not None and summary.failed > 0:
        parts.append(f"❌ Failed: {summary.failed}")
    if summary.error is not None and summary.error > 0:
        parts.append(f"⚠️ Error: {summary.error}")
    if summary.skipped is not None and summary.skipped > 0:
        parts.append(f"⏭️ Skipped: {summary.skipped}")
    if summary.xfailed is not None and summary.xfailed > 0:
        parts.append(f"🔶 Expected failures: {summary.xfailed}")
    if summary.xpassed is not None and summary.xpassed > 0:
        parts.append(f"🔶 Unexpected passes: {summary.xpassed}")

    return " | ".join(parts)
