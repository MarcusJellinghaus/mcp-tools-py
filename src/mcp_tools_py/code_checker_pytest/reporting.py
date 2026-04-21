"""
Functions for formatting and reporting pytest test results.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from mcp_tools_py.log_utils import log_function_call

from mcp_tools_py.code_checker_pytest.models import Collector, PytestReport, Test

logger = logging.getLogger(__name__)
# Constants to avoid magic numbers
MAX_OUTPUT_LINES = 300
MAX_FAILURES = 10
SMALL_TEST_RUN_THRESHOLD = 3
FAILED_OUTCOMES = ["failed", "error"]


class OutputBuilder:
    """
    Helper class to manage output building with line counting and truncation.
    """

    def __init__(self, max_lines: int = MAX_OUTPUT_LINES):
        self.parts: List[str] = []
        self.line_count = 0
        self.max_lines = max_lines
        self.truncated = False

    def add(self, content: str) -> bool:
        """
        Add content to the output, checking line limits.

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
        """Get the final output string."""
        return "".join(self.parts)


def should_show_details(_test_results: Dict[str, Any], show_details: bool) -> bool:
    """
    Determine if detailed output should be shown based on test results and user preference.

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
    """Extract failed collectors from test session result."""
    if not test_session_result.collectors:
        return []

    return [
        collector
        for collector in test_session_result.collectors
        if collector.outcome in FAILED_OUTCOMES
    ]


def _get_failed_tests(
    test_session_result: PytestReport, max_failures: int
) -> List[Test]:
    """Extract and limit failed tests from test session result."""
    if not test_session_result.tests:
        return []

    failed_tests = [
        test for test in test_session_result.tests if test.outcome in FAILED_OUTCOMES
    ]

    return failed_tests[:max_failures]


def _format_collector_info(collector: Collector, output: OutputBuilder) -> bool:
    """
    Format information about a failed collector.

    Args:
        collector: The failed collector to format
        output: OutputBuilder instance to add content to

    Returns:
        True if successful, False if truncated
    """
    if not output.add(
        f"Collector ID: {collector.nodeid} - outcome {collector.outcome}\n"
    ):
        return False

    # Collection errors are always shown (critical setup issues)
    if collector.longrepr:
        if not output.add(f"  Longrepr: {collector.longrepr}\n"):
            return False

    if collector.result:
        for result in collector.result:
            if not output.add(f"  Result: {result}\n"):
                return False

    return output.add("\n")


def _format_test_output(
    test: Test, output: OutputBuilder, include_print_output: bool
) -> bool:
    """
    Format stdout, stderr, and longrepr output for a test.

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
    """
    Format setup information for a failed test.

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
    """
    Format information about a failed test.

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


def _process_failed_collectors(
    failed_collectors: List[Collector], output: OutputBuilder
) -> bool:
    """
    Process and format all failed collectors.

    Args:
        failed_collectors: List of failed collectors
        output: OutputBuilder instance

    Returns:
        True if successful, False if truncated
    """
    if not failed_collectors:
        return True

    if not output.add("The following collectors failed during the test session:\n"):
        return False

    for collector in failed_collectors:
        if not _format_collector_info(collector, output):
            return False

    return True


def _process_failed_tests(
    failed_tests: List[Test],
    output: OutputBuilder,
    include_print_output: bool,
    max_number_of_tests_reported: int,
) -> bool:
    """
    Process and format failed tests.

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
    """
    Creates a prompt for an LLM based on the failed tests from a test session result.

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

    # Get failed collectors and tests
    failed_collectors = _get_failed_collectors(test_session_result)
    failed_tests = _get_failed_tests(test_session_result, max_failures)

    # Process failed collectors (always shown - critical setup issues)
    if not _process_failed_collectors(failed_collectors, output):
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


def get_detailed_test_summary(
    test_session_result: PytestReport, show_details: bool
) -> str:
    """
    Enhanced summary that can include additional detail hints.

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


def get_test_summary(test_session_result: PytestReport) -> str:
    """
    Generate a human-readable summary of the test results.

    Args:
        test_session_result: The test session result to summarize

    Returns:
        A string with the test summary
    """
    summary = test_session_result.summary

    parts = []
    parts.append(
        f"Collected {summary.collected} tests in {test_session_result.duration:.2f} seconds"
    )

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
