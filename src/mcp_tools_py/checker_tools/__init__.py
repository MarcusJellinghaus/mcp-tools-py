"""CheckerTools orchestrator. Public API: from mcp_tools_py.checker_tools import CheckerTools."""

import logging
from typing import TYPE_CHECKING, Any, Optional

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
from mcp_tools_py.code_checker_pytest.reporting import (
    MAX_FAILURES,
    MAX_OUTPUT_LINES,
    create_prompt_for_failed_tests,
    create_prompt_for_passing_output,
    should_show_details,
)
from mcp_tools_py.code_checker_pytest.verdict import (
    RunStatus,
    format_collection_problems,
    format_error_text,
    format_suspicious_text,
)

if TYPE_CHECKING:
    from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol
    from mcp_tools_py.utils.tool_context import ToolContext

logger = logging.getLogger(__name__)


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

    def _format_pylint_result(self, pylint_prompt: Optional[str]) -> str:
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
    ) -> str:
        """Format a pytest run by its verdict status; only PASSED reads as completed.

        With show_output, a passing run also lists the captured output of passing tests.
        ERROR and unknown statuses fail closed and render the shared error text.

        Returns:
            User-facing summary of the pytest outcome.
        """
        verdict = test_results["verdict"]
        report = test_results.get("test_results")

        summary = test_results.get("summary", {})
        if not isinstance(summary, dict):
            return "Error: Invalid test summary format"

        if verdict.status is RunStatus.PASSED:
            if test_results.get("summary_text"):
                result = f"Pytest check completed. {test_results['summary_text']}"
            else:
                passed_count = summary.get("passed") or 0
                result = f"Pytest check completed. All {passed_count} tests passed successfully."
            if show_output and report:
                result += "\n\n" + create_prompt_for_passing_output(report)
            return result
        if verdict.status is RunStatus.FAILED:
            if report is None or not should_show_details(test_results, show_details):
                return f"Pytest found failures. {test_results.get('summary_text') or ''}".rstrip()
            block = format_collection_problems(report, verdict)
            failed_tests_prompt = create_prompt_for_failed_tests(
                report,
                max_number_of_tests_reported=MAX_FAILURES,
                include_print_output=True,
                max_failures=MAX_FAILURES,
                max_output_lines=MAX_OUTPUT_LINES,
            )
            text = f"Pytest found issues that need attention:\n\n{failed_tests_prompt}"
            return f"{block}\n\n{text}" if block else text
        if verdict.status is RunStatus.SUSPICIOUS:
            return format_suspicious_text(summary.get("collected") or 0)
        return format_error_text(report, verdict)

    def _format_mypy_result(self, mypy_prompt: str | None) -> str:
        """Format mypy check result.

        Returns:
            User-facing summary of the mypy outcome.
        """
        if mypy_prompt is None:
            return "Mypy check completed. No type errors found."
        return mypy_prompt


__all__ = ["CheckerTools"]
