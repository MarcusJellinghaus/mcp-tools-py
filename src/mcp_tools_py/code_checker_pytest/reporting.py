"""Functions for formatting and reporting pytest test results."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    PytestReport,
    Summary,
    Test,
)
from mcp_tools_py.log_utils import log_function_call

logger = logging.getLogger(__name__)
# Constants to avoid magic numbers
MAX_OUTPUT_LINES = 300
MAX_FAILURES = 10
FAILED_OUTCOMES = ["failed", "error"]
NO_CAPTURED_OUTPUT_NOTE = "Note: no passing test produced captured output."
XDIST_MARKER = "Different tests were collected"
MAX_COLLECTOR_IDS = 10


class OutputBuilder:
    """Helper class to manage output building with line counting and truncation."""

    def __init__(self, max_lines: int = MAX_OUTPUT_LINES):
        self.parts: List[str] = []
        self.line_count = 0
        self.max_lines = max_lines
        self.truncated = False

    def add(self, content: str) -> bool:
        """Add content to the output, checking line limits.

        Args:
            content: Content to add

        Returns:
            True if content was added, False if truncated
        """
        if self.truncated:
            return False

        lines = content.count("\n")
        if self.line_count + lines > self.max_lines:
            remaining_lines = self.max_lines - self.line_count
            if remaining_lines > 0:
                content_lines = content.split("\n")
                self.parts.append("\n".join(content_lines[:remaining_lines]))
                self.parts.append(
                    f"\n\n[Output truncated at {self.max_lines} lines...]\n"
                )
            self.truncated = True
            return False

        self.parts.append(content)
        self.line_count += lines
        return True

    def get_result(self) -> str:
        """Get the final output string.

        Returns:
            All appended parts concatenated.
        """
        return "".join(self.parts)


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


def _get_failed_tests(
    test_session_result: PytestReport, max_failures: int
) -> List[Test]:
    """Extract and limit failed tests from test session result.

    Returns:
        Up to `max_failures` failed/errored tests.
    """
    if not test_session_result.tests:
        return []

    failed_tests = [
        test for test in test_session_result.tests if test.outcome in FAILED_OUTCOMES
    ]

    return failed_tests[:max_failures]


def _format_test_output(
    test: Test, output: OutputBuilder, include_print_output: bool
) -> bool:
    """Format stdout, stderr, and longrepr output for a test.

    Args:
        test: The test to format output for
        output: OutputBuilder instance
        include_print_output: Whether to include print output

    Returns:
        True if successful, False if truncated
    """
    if not include_print_output or not test.call:
        return True

    if test.call.stdout:
        if not output.add(f"  Stdout:\n```\n{test.call.stdout}\n```\n"):
            return False

    if test.call.stderr:
        if not output.add(f"  Stderr:\n```\n{test.call.stderr}\n```\n"):
            return False

    if test.call.longrepr:
        if not output.add(f"  Longrepr:\n```\n{test.call.longrepr}\n```\n"):
            return False

    return True


def _format_test_setup_info(
    test: Test, output: OutputBuilder, include_print_output: bool
) -> bool:
    """Format setup information for a failed test.

    Args:
        test: The test with failed setup
        output: OutputBuilder instance
        include_print_output: Whether to include print output

    Returns:
        True if successful, False if truncated
    """
    if not test.setup or test.setup.outcome != "failed":
        return True

    if not output.add(f"  Test Setup Outcome: {test.setup.outcome}\n"):
        return False

    if test.setup.crash:
        if not output.add(
            f"  Test Setup Crash Error Message: {test.setup.crash.message}\n"
        ):
            return False
        if not output.add(f"  Test Setup Crash Error Path: {test.setup.crash.path}\n"):
            return False
        if not output.add(f"  Setup Crash Error Line: {test.setup.crash.lineno}\n"):
            return False

    if test.setup.traceback:
        if not output.add("  Test Setup Traceback:\n"):
            return False
        for entry in test.setup.traceback:
            if not output.add(f"   - {entry.path}:{entry.lineno} - {entry.message}\n"):
                return False

    # Include setup output sections only if include_print_output is True
    if include_print_output:
        if test.setup.stdout:
            if not output.add(f"  Test Setup Stdout:\n```\n{test.setup.stdout}\n```\n"):
                return False
        if test.setup.stderr:
            if not output.add(f"  Test Setup Stderr:\n```\n{test.setup.stderr}\n```\n"):
                return False
        if test.setup.longrepr:
            if not output.add(
                f"  Test Setup Longrepr:\n```\n{test.setup.longrepr}\n```\n"
            ):
                return False

    return True


def _format_test_info(
    test: Test, output: OutputBuilder, include_print_output: bool
) -> bool:
    """Format information about a failed test.

    Args:
        test: The failed test to format
        output: OutputBuilder instance
        include_print_output: Whether to include print output

    Returns:
        True if successful, False if truncated
    """
    if not output.add(f"Test ID: {test.nodeid} - outcome {test.outcome}\n"):
        return False

    # Format crash information
    if test.call and test.call.crash:
        if not output.add(f"  Error Message: {test.call.crash.message}\n"):
            return False

    # Format traceback
    if test.call and test.call.traceback:
        if not output.add("  Traceback:\n"):
            return False
        for entry in test.call.traceback:
            if not output.add(f"   - {entry.path}:{entry.lineno} - {entry.message}\n"):
                return False

    # Format test output (stdout, stderr, longrepr)
    if not _format_test_output(test, output, include_print_output):
        return False

    # Format setup information if setup failed
    if not _format_test_setup_info(test, output, include_print_output):
        return False

    return True


def _process_failed_collectors(report: PytestReport, output: OutputBuilder) -> bool:
    """Add the count line and one group per distinct collector error.

    Args:
        report: The parsed pytest report
        output: OutputBuilder instance

    Returns:
        True if successful or no collector failed, False if truncated
    """
    line = collectors_failed_line(report)
    if not line:
        return True

    if not output.add(f"{line}\n\n"):
        return False

    return all(output.add(f"{group}\n\n") for group in group_failed_collectors(report))


def _process_failed_tests(
    failed_tests: List[Test],
    output: OutputBuilder,
    include_print_output: bool,
    max_number_of_tests_reported: int,
) -> bool:
    """Process and format failed tests.

    Args:
        failed_tests: List of failed tests
        output: OutputBuilder instance
        include_print_output: Whether to include print output
        max_number_of_tests_reported: Maximum number of tests to report

    Returns:
        True if successful, False if truncated
    """
    if not failed_tests:
        return True

    if not output.add("The following tests failed during the test session:\n"):
        return False

    test_count = 0
    for test in failed_tests:
        if not _format_test_info(test, output, include_print_output):
            return False

        if not output.add("\n"):
            return False

        test_count += 1
        if test_count >= max_number_of_tests_reported:
            break

        if not output.add(
            "===============================================================================\n"
        ):
            return False
        if not output.add("\n"):
            return False

    return True


@log_function_call
def create_prompt_for_failed_tests(
    test_session_result: PytestReport,
    max_number_of_tests_reported: int = 1,
    include_print_output: bool = True,
    max_failures: int = MAX_FAILURES,
    max_output_lines: int = MAX_OUTPUT_LINES,
) -> Optional[str]:
    """Creates a prompt for an LLM based on the failed tests from a test session result.

    Args:
        test_session_result: The test session result to analyze
        max_number_of_tests_reported: Maximum number of tests to include in the prompt
        include_print_output: Whether to include stdout/stderr/longrepr output
        max_failures: Maximum number of failures to report
        max_output_lines: Overall output line limit with truncation indicator

    Returns:
        A prompt string, or None if no tests failed
    """
    output = OutputBuilder(max_output_lines)

    failed_tests = _get_failed_tests(test_session_result, max_failures)

    # Process failed collectors (always shown - critical setup issues)
    if not _process_failed_collectors(test_session_result, output):
        return output.get_result()

    # Process failed tests
    if not _process_failed_tests(
        failed_tests, output, include_print_output, max_number_of_tests_reported
    ):
        return output.get_result()

    # Add closing question if we have content
    if output.parts:
        output.add(
            "Can you provide an explanation for why these tests failed and suggest how they could be fixed?"
        )
        return output.get_result()

    return None


@log_function_call
def create_prompt_for_passing_output(
    test_session_result: PytestReport,
    max_output_lines: int = MAX_OUTPUT_LINES,
) -> str:
    """List the captured stdout and stderr of tests that did not fail.

    Covers the setup, call and teardown stages. Longrepr is never shown.

    Args:
        test_session_result: The test session result to read output from
        max_output_lines: Overall output line limit with truncation indicator

    Returns:
        The captured output per test, or NO_CAPTURED_OUTPUT_NOTE if no test printed
    """
    output = OutputBuilder(max_output_lines)
    any_added = False

    for test in test_session_result.tests or []:
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

        if not any_added:
            any_added = True
            if not output.add("Captured output of passing tests:\n"):
                break
        if not output.add(f"Test ID: {test.nodeid} - outcome {test.outcome}\n"):
            break
        if not all(
            output.add(f"  {label}:\n```\n{text}\n```\n") for label, text in blocks
        ):
            break

    return output.get_result() if any_added else NO_CAPTURED_OUTPUT_NOTE


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
