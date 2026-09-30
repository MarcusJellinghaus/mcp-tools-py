"""Tests for CheckerTools registration and result formatting."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_mypy.reporting import MYPY_FAILURE_PREFIX
from mcp_tools_py.code_checker_pytest.models import PytestReport
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.utils.tool_context import ToolContext


@pytest.fixture
def checker_tools(tool_context: ToolContext) -> CheckerTools:
    """Create a CheckerTools instance over the shared context."""
    return CheckerTools(tool_context)


# --- Registration tests ---


def test_checker_tools_registers_nine_tools(tool_context: ToolContext) -> None:
    """Test that CheckerTools.register() registers exactly 9 tools on an MCP server."""
    mock_mcp = MagicMock()
    mock_decorator = MagicMock(side_effect=lambda fn: fn)
    mock_mcp.tool.return_value = mock_decorator

    checker = CheckerTools(tool_context)
    checker.register(mock_mcp)

    # 9 tools: run_pylint_check, run_pytest_check, run_mypy_check,
    # run_lint_imports_check, run_vulture_check, run_ruff_check, run_ruff_fix,
    # run_bandit_check, run_tach_check
    assert mock_mcp.tool.call_count == 9


# --- Pylint formatting tests ---


def test_format_pylint_result_no_issues(checker_tools: CheckerTools) -> None:
    """Test formatting when pylint finds no issues."""
    result = checker_tools._format_pylint_result(None)
    assert "No issues found" in result


def test_format_pylint_result_with_issues(checker_tools: CheckerTools) -> None:
    """Test formatting when pylint finds issues."""
    prompt = "pylint found some issues related to code W0612."
    result = checker_tools._format_pylint_result(prompt)
    assert result == prompt


# --- Mypy formatting tests ---


def test_format_mypy_result_no_issues(checker_tools: CheckerTools) -> None:
    """Test formatting when mypy finds no type errors."""
    result = checker_tools._format_mypy_result(None)
    assert "No type errors found" in result


def test_format_mypy_result_with_issues(checker_tools: CheckerTools) -> None:
    """A report already carries its own header and is passed through unchanged."""
    prompt = (
        "Mypy found type issues that need attention:\n\n"
        "mypy found 1 issue across 1 rule"
    )
    result = checker_tools._format_mypy_result(prompt)
    assert result == prompt


def test_format_mypy_result_failure_keeps_its_own_headline(
    checker_tools: CheckerTools,
) -> None:
    """A failure prompt already names itself and is returned as-is."""
    prompt = f"{MYPY_FAILURE_PREFIX} timed out after 120 seconds"
    result = checker_tools._format_mypy_result(prompt)
    assert result == prompt
    assert "Mypy found type issues" not in result


# --- Pytest formatting tests ---


def test_format_pytest_result_success(checker_tools: CheckerTools) -> None:
    """Test formatting for a successful pytest run."""
    test_results: dict[str, Any] = {
        "success": True,
        "summary": {
            "passed": 10,
            "failed": 0,
            "error": 0,
            "collected": 10,
            "duration": 2.3,
        },
        "test_results": None,
        "summary_text": "10 passed in 2.30s",
    }
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Pytest check completed" in result
    assert "10" in result


def test_format_pytest_result_failure(checker_tools: CheckerTools) -> None:
    """Test formatting for a failed pytest run."""
    test_results: dict[str, Any] = {
        "success": True,
        "summary": {
            "passed": 5,
            "failed": 2,
            "error": 0,
            "collected": 7,
            "duration": 1.5,
        },
        "test_results": MagicMock(),
    }
    with patch(
        "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
    ) as mock_prompt:
        mock_prompt.return_value = "Detailed failure info..."
        result = checker_tools._format_pytest_result_with_details(
            test_results, show_details=True
        )
    assert "Pytest found issues" in result
    assert "Detailed failure info..." in result


def _passing_report_with_output() -> PytestReport:
    """Build a passing PytestReport whose one test printed to stdout."""
    return parse_pytest_report(
        json.dumps(
            {
                "created": 0.0,
                "duration": 0.1,
                "exitcode": 0,
                "root": "/project",
                "environment": {},
                "summary": {"collected": 1, "passed": 1, "total": 1},
                "collectors": [],
                "tests": [
                    {
                        "nodeid": "tests/test_a.py::test_prints",
                        "lineno": 1,
                        "keywords": [],
                        "outcome": "passed",
                        "call": {
                            "duration": 0.001,
                            "outcome": "passed",
                            "stdout": "HELLO\n",
                        },
                    }
                ],
                "warnings": [],
            }
        )
    )


def _passing_results() -> dict[str, Any]:
    """Build the results dict of a passing run whose test printed."""
    return {
        "success": True,
        "summary": {"passed": 1, "failed": 0, "error": 0, "collected": 1},
        "test_results": _passing_report_with_output(),
        "summary_text": "1 passed in 0.10s",
    }


def test_format_pytest_result_success_with_show_output(
    checker_tools: CheckerTools,
) -> None:
    """With show_output, a passing run adds the captured output after the summary."""
    result = checker_tools._format_pytest_result_with_details(
        _passing_results(), show_details=True, show_output=True
    )
    assert result.startswith("Pytest check completed. 1 passed in 0.10s\n\n")
    assert "Captured output of passing tests:" in result
    assert "HELLO" in result


def test_format_pytest_result_success_without_show_output(
    checker_tools: CheckerTools,
) -> None:
    """Without show_output, a passing run returns only the summary line."""
    result = checker_tools._format_pytest_result_with_details(
        _passing_results(), show_details=True
    )
    assert result == "Pytest check completed. 1 passed in 0.10s"


def test_format_pytest_result_failure_ignores_show_output(
    checker_tools: CheckerTools,
) -> None:
    """A failing run keeps the failed-tests prompt and adds no passing output."""
    test_results: dict[str, Any] = {
        "success": True,
        "summary": {"passed": 1, "failed": 1, "error": 0, "collected": 2},
        "test_results": _passing_report_with_output(),
    }
    with patch(
        "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
    ) as mock_prompt:
        mock_prompt.return_value = "Detailed failure info..."
        result = checker_tools._format_pytest_result_with_details(
            test_results, show_details=True, show_output=True
        )
    mock_prompt.assert_called_once()
    assert "Detailed failure info..." in result
    assert "Captured output of passing tests" not in result


def test_format_pytest_result_execution_error(checker_tools: CheckerTools) -> None:
    """Test formatting when pytest fails to execute."""
    test_results: dict[str, Any] = {
        "success": False,
        "error": "No module named 'pytest'",
    }
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Error running pytest" in result
    assert "No module named 'pytest'" in result
