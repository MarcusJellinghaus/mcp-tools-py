"""CheckerTools orchestrator. Public API: from mcp_tools_py.checker_tools import CheckerTools."""

import logging
from typing import TYPE_CHECKING, Any

from mcp_tools_py.checker_tools import (
    bandit_tool,
    deptry_tool,
    lint_imports_tool,
    mypy_tool,
    pylint_tool,
    pytest_tool,
    ruff_check_tool,
    ruff_fix_tool,
    tach_tool,
    vulture_tool,
)
from mcp_tools_py.code_checker_mypy.reporting import MYPY_SUCCESS_TEXT
from mcp_tools_py.code_checker_pytest.models import PytestReport
from mcp_tools_py.code_checker_pytest.report_extras import skipped_block
from mcp_tools_py.code_checker_pytest.reporting import (
    ALL_CAPTURE,
    DROPPED_NOTICE,
    MIN_FENCED_LINES,
    create_prompt_for_failed_tests,
    create_prompt_for_passing_output,
    did_not_run_line,
    should_show_details,
    warnings_part,
)
from mcp_tools_py.code_checker_pytest.verdict import (
    RunStatus,
    format_collect_only_text,
    format_collection_problems,
    format_error_text,
    format_suspicious_text,
)
from mcp_tools_py.utils.report_budget import MAX_FAILURES, TOOL_CHARS, TOOL_LINES

if TYPE_CHECKING:
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol
    from mcp_tools_py.utils.tool_context import ToolContext

logger = logging.getLogger(__name__)


def _with_passing_output(
    text: str, report: PytestReport, max_lines: int, max_chars: int
) -> str:
    """Append the passing-test output (-s) within what `text` left of the budget.

    Returns:
        `text`, a blank line, then the passing output; or the dropped notice
        when fewer than MIN_FENCED_LINES lines are left.
    """
    lines_left = max_lines - text.count("\n") - 3
    chars_left = max_chars - len(text) - 2
    if lines_left < MIN_FENCED_LINES:
        return f"{text}\n\n{DROPPED_NOTICE} passing-test output (-s)"
    return f"{text}\n\n" + create_prompt_for_passing_output(
        report, lines_left, chars_left
    )


class CheckerTools:
    """Registers pylint, pytest, mypy, lint-imports, vulture, ruff check, ruff fix, bandit, deptry, and tach checker tools on an MCP server."""

    def __init__(self, context: "ToolContext") -> None:
        self.context = context

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all checker tools with the MCP server."""
        pylint_tool.register(mcp, self)
        pytest_tool.register(mcp, self)
        mypy_tool.register(mcp, self)
        lint_imports_tool.register(mcp, self)
        vulture_tool.register(mcp, self)
        ruff_check_tool.register(mcp, self)
        ruff_fix_tool.register(mcp, self)
        bandit_tool.register(mcp, self)
        deptry_tool.register(mcp, self)
        tach_tool.register(mcp, self)

    def _format_pylint_result(self, pylint_prompt: str | None) -> str:
        """Format pylint check result.

        Returns:
            User-facing summary of the pylint outcome.
        """
        if pylint_prompt is None:
            return "Pylint check completed. No issues found that require attention."
        return pylint_prompt

    def _format_pytest_result_with_details(
        self,
        test_results: dict[str, Any],
        show_details: bool,
        show_output: bool = False,
        collect_only: bool = False,
        max_lines: int = TOOL_LINES,
        max_chars: int = TOOL_CHARS,
        capture: frozenset[str] = ALL_CAPTURE,
    ) -> str:
        """Format a pytest run by its verdict status; only PASSED reads as completed.

        With show_output and a report that has tests, PASSED, FAILED and ERROR
        append the captured output of passing tests after their main text,
        within what that text left of the budget (failures take priority).
        `capture` selects the captured kinds shown in failing-test blocks.
        With collect_only, a run with no outcomes lists the selected test IDs.
        PASSED, FAILED and ERROR append the report's warnings count to their counts.
        ERROR and unknown statuses fail closed and render the shared error text;
        an exit-5 run's `skip_report` appends its skip block after it.
        `max_lines` and `max_chars` bound the failure prompt, the passing output
        and the error text with its skip block.

        Returns:
            User-facing summary of the pytest outcome.
        """
        verdict = test_results["verdict"]
        report = test_results.get("test_results")

        summary = test_results.get("summary", {})
        if not isinstance(summary, dict):
            return "Error: Invalid test summary format"

        summary_text = test_results.get("summary_text") or ""
        if summary_text:
            summary_text += warnings_part(report)

        def finish(text: str) -> str:
            if show_output and report is not None and report.tests:
                return _with_passing_output(text, report, max_lines, max_chars)
            return text

        if verdict.status is RunStatus.PASSED:
            if summary_text:
                result = f"Pytest check completed. {summary_text}"
            else:
                passed_count = summary.get("passed") or 0
                result = f"Pytest check completed. All {passed_count} tests passed successfully."
            return finish(result)
        if verdict.status is RunStatus.FAILED:
            if report is None or not should_show_details(test_results, show_details):
                return finish(f"Pytest found failures. {summary_text}".rstrip())
            failed_tests_prompt = create_prompt_for_failed_tests(
                report,
                capture=capture,
                max_failures=MAX_FAILURES,
                max_lines=max_lines,
                max_chars=max_chars,
            )
            counts = "\n".join(filter(None, [summary_text, did_not_run_line(report)]))
            text = f"Pytest found issues that need attention:\n\n{failed_tests_prompt}"
            return finish(
                "\n\n".join(
                    filter(None, [counts, format_collection_problems(verdict), text])
                )
            )
        if verdict.status is RunStatus.SUSPICIOUS:
            if collect_only and report:
                return format_collect_only_text(report)
            return format_suspicious_text(
                summary.get("collected") or 0, summary.get("deselected")
            )
        text = format_error_text(report, verdict, show_warnings=True)
        skip_report = test_results.get("skip_report")
        if skip_report is not None:
            block = skipped_block(
                skip_report,
                max_lines - len(text.splitlines()) - 1,
                max_chars - len(text) - 1,
            )
            if block:
                text += "\n" + block
        return finish(text)

    def _format_mypy_result(self, mypy_prompt: str | None) -> str:
        """Format mypy check result.

        Returns:
            User-facing summary of the mypy outcome.
        """
        if mypy_prompt is None:
            return MYPY_SUCCESS_TEXT
        return mypy_prompt


__all__ = ["CheckerTools"]
