"""Tests for CheckerTools registration and result formatting."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_mypy.reporting import MYPY_FAILURE_PREFIX
from mcp_tools_py.code_checker_pytest.models import ErrorContext, PytestReport, Summary
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.code_checker_pytest.verdict import (
    RunStatus,
    RunVerdict,
    classify_run,
)
from mcp_tools_py.utils.tool_context import ToolContext
from tests._pytest_results import make_pytest_results


@pytest.fixture
def checker_tools(tool_context: ToolContext) -> CheckerTools:
    """Create a CheckerTools instance over the shared context."""
    return CheckerTools(tool_context)


# --- Registration tests ---


def test_checker_tools_registers_ten_tools(tool_context: ToolContext) -> None:
    """Test that CheckerTools.register() registers exactly 10 tools on an MCP server."""
    mock_mcp = MagicMock()
    mock_decorator = MagicMock(side_effect=lambda fn: fn)
    mock_mcp.tool.return_value = mock_decorator

    checker = CheckerTools(tool_context)
    checker.register(mock_mcp)

    # 10 tools: run_pylint_check, run_pytest_check, run_mypy_check,
    # run_lint_imports_check, run_vulture_check, run_ruff_check, run_ruff_fix,
    # run_bandit_check, run_deptry_check, run_tach_check
    assert mock_mcp.tool.call_count == 10


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
    test_results = make_pytest_results(
        summary={
            "passed": 10,
            "failed": 0,
            "error": 0,
            "collected": 10,
            "duration": 2.3,
        },
        test_results=None,
        summary_text="10 passed in 2.30s",
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Pytest check completed" in result
    assert "10" in result


def test_format_pytest_result_failure(checker_tools: CheckerTools) -> None:
    """Test formatting for a failed pytest run."""
    test_results = make_pytest_results(
        RunStatus.FAILED,
        summary={
            "passed": 5,
            "failed": 2,
            "error": 0,
            "collected": 7,
            "duration": 1.5,
        },
        test_results=MagicMock(),
    )
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
    return make_pytest_results(
        summary={"passed": 1, "failed": 0, "error": 0, "collected": 1},
        test_results=_passing_report_with_output(),
        summary_text="1 passed in 0.10s",
    )


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
    test_results = make_pytest_results(
        RunStatus.FAILED,
        summary={"passed": 1, "failed": 1, "error": 0, "collected": 2},
        test_results=_passing_report_with_output(),
    )
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
    test_results = make_pytest_results(RunStatus.ERROR, ["No module named 'pytest'"])
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Pytest run" in result
    assert "did not complete" in result
    assert "No module named 'pytest'" in result
    assert "completed" not in result


def _failed_report(collection_errors: list[str] | None = None) -> PytestReport:
    """Build a real FAILED report (exit 1) with only error_message unless given."""
    return PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=1,
        root="/project",
        environment={},
        summary=Summary(collected=2, total=2, passed=1, failed=1),
        collectors=[],
        tests=[],
        error_context=ErrorContext(
            exit_code=1,
            exit_code_meaning="Tests failed",
            error_message="full pytest output\n1 failed, 1 passed",
            suggestion="",
            collection_errors=collection_errors,
        ),
    )


def test_format_pytest_result_failed_with_collection_errors(
    checker_tools: CheckerTools,
) -> None:
    """Collection errors precede the failure prompt in a FAILED run."""
    report = _failed_report(["ERROR tests/test_x.py - ImportError: boom"])
    test_results = make_pytest_results(
        summary={"passed": 1, "failed": 1, "collected": 2},
        test_results=report,
        verdict=classify_run(report),
    )
    with patch(
        "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
    ) as mock_prompt:
        mock_prompt.return_value = "Detailed failure info..."
        result = checker_tools._format_pytest_result_with_details(
            test_results, show_details=True
        )
    assert result.startswith("Collection problems:\n")
    assert "ImportError: boom" in result
    assert result.index("ImportError: boom") < result.index(
        "Pytest found issues that need attention:"
    )
    assert result.endswith("Detailed failure info...")


def test_format_pytest_result_plain_failed_has_no_collection_block(
    checker_tools: CheckerTools,
) -> None:
    """A plain FAILED run does not turn its error_message into a problems block."""
    report = _failed_report()
    test_results = make_pytest_results(
        summary={"passed": 1, "failed": 1, "collected": 2},
        test_results=report,
        verdict=classify_run(report),
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Collection problems:" not in result
    assert result.startswith("Pytest found issues that need attention:")


def test_format_pytest_result_failed_without_report(
    checker_tools: CheckerTools,
) -> None:
    """Without a report, FAILED gives the short failure line."""
    test_results = make_pytest_results(
        RunStatus.FAILED,
        summary={"passed": 1, "failed": 1, "collected": 2},
        test_results=None,
        summary_text="1 failed, 1 passed",
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert result == "Pytest found failures. 1 failed, 1 passed"
    assert "completed" not in result


def test_format_pytest_result_failed_show_details_false(
    checker_tools: CheckerTools,
) -> None:
    """show_details=False gives the same short line as a missing report."""
    test_results = make_pytest_results(
        RunStatus.FAILED,
        summary={"passed": 1, "failed": 1, "collected": 2},
        test_results=_failed_report(),
        summary_text="1 failed, 1 passed",
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=False
    )
    assert result == "Pytest found failures. 1 failed, 1 passed"


def test_format_pytest_result_suspicious(checker_tools: CheckerTools) -> None:
    """SUSPICIOUS is reported as not verified, never completed."""
    test_results = make_pytest_results(
        RunStatus.SUSPICIOUS,
        summary={"collected": 5},
        test_results=None,
        summary_text="Collected 5 tests",
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Not verified" in result
    assert "completed" not in result


def test_format_pytest_result_error_with_report(checker_tools: CheckerTools) -> None:
    """ERROR with a report shows the headline, counts and exit-code line."""
    report = PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=1,
        root="/project",
        environment={},
        summary=Summary(collected=5, total=5, passed=5),
    )
    test_results = make_pytest_results(
        summary={"passed": 5, "collected": 5},
        test_results=report,
        verdict=RunVerdict(RunStatus.ERROR, ["something broke"], 1),
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "reported an error" in result
    assert "5" in result
    assert "Exit code 1" in result
    assert "completed" not in result


def test_format_pytest_result_unknown_status_fails_closed(
    checker_tools: CheckerTools,
) -> None:
    """An unrecognised status renders the error text, never completed."""
    test_results = make_pytest_results(
        summary={"passed": 3, "collected": 3},
        test_results=None,
        verdict=MagicMock(status="bogus", problems=["x"], exit_code=1),
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Pytest run reported an error." in result
    assert "Exit code 1" in result
    assert "completed" not in result
