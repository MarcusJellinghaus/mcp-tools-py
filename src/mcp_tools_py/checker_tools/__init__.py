"""CheckerTools orchestrator. Public API: from mcp_tools_py.checker_tools import CheckerTools."""

import logging
from typing import TYPE_CHECKING, Any, Optional

from mcp_tools_py.checker_tools import (
    bandit_tool,
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
    SMALL_TEST_RUN_THRESHOLD,
    create_prompt_for_failed_tests,
    should_show_details,
)

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol, ToolServer

logger = logging.getLogger(__name__)


class CheckerTools:
    """Registers pylint, pytest, mypy, lint-imports, vulture, ruff check, ruff fix, bandit, and tach checker tools on an MCP server."""

    def __init__(self, server: "ToolServer") -> None:
        self._server = server

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
        self, test_results: dict[str, Any], show_details: bool
    ) -> str:
        """Enhanced formatting that respects show_details parameter.

        Returns:
            User-facing summary of the pytest outcome.
        """
        if not test_results["success"]:
            return f"Error running pytest: {test_results.get('error', 'Unknown error')}"

        summary = test_results.get("summary", {})
        if not isinstance(summary, dict):
            return "Error: Invalid test summary format"

        # Handle None values properly
        failed_count = summary.get("failed") or 0
        error_count = summary.get("error") or 0
        passed_count = summary.get("passed") or 0
        collected = summary.get("collected") or 0

        # Determine if we have failures that need attention
        failures_exist = (failed_count > 0 or error_count > 0) and test_results.get(
            "test_results"
        )

        if failures_exist:
            should_show = should_show_details(test_results, show_details)

            if should_show:
                # Use enhanced create_prompt_for_failed_tests with new parameters
                failed_tests_prompt = create_prompt_for_failed_tests(
                    test_results["test_results"],
                    max_number_of_tests_reported=MAX_FAILURES,  # Use constant
                    include_print_output=True,
                    max_failures=MAX_FAILURES,
                    max_output_lines=MAX_OUTPUT_LINES,  # Use constant
                )
                return (
                    f"Pytest found issues that need attention:\n\n{failed_tests_prompt}"
                )
            else:
                # NOTE: This branch is currently dead code -- show_details is
                # always passed as True from run_pytest_check().  Retained for
                # possible future use.  The hint below references the removed
                # show_details parameter and would need updating if re-enabled.
                hint = (
                    " Try show_details=True for more information."
                    if collected <= SMALL_TEST_RUN_THRESHOLD
                    else ""
                )
                return f"Pytest completed with failures.{hint}"
        else:
            # Success case - use existing logic
            if test_results.get("summary_text"):
                return f"Pytest check completed. {test_results['summary_text']}"
            else:
                return f"Pytest check completed. All {passed_count} tests passed successfully."

    def _format_mypy_result(self, mypy_prompt: str | None) -> str:
        """Format mypy check result.

        Returns:
            User-facing summary of the mypy outcome.
        """
        if mypy_prompt is None:
            return "Mypy check completed. No type errors found."
        # A failure already names itself -- don't announce it as type issues
        if mypy_prompt.startswith("Mypy execution failed:"):
            return mypy_prompt
        return f"Mypy found type issues that need attention:\n\n{mypy_prompt}"


__all__ = ["CheckerTools"]
