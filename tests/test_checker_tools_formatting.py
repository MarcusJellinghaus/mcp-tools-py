"""Tests for CheckerTools registration and result formatting."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_mypy.reporting import MYPY_FAILURE_PREFIX
from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    CollectorResult,
    ErrorContext,
    PytestReport,
    Summary,
)
from mcp_tools_py.code_checker_pytest.models import Warning as ReportWarning
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.code_checker_pytest.reporting import DROPPED_NOTICE, XDIST_MARKER
from mcp_tools_py.code_checker_pytest.verdict import (
    XDIST_HINT,
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
        test_results=MagicMock(summary=Summary(collected=7, total=7)),
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


def _mixed_report() -> PytestReport:
    """Build a report with one failing test and one passing test that printed."""
    return parse_pytest_report(
        json.dumps(
            {
                "created": 0.0,
                "duration": 0.1,
                "exitcode": 1,
                "root": "/project",
                "environment": {},
                "summary": {"collected": 2, "passed": 1, "failed": 1, "total": 2},
                "collectors": [],
                "tests": [
                    {
                        "nodeid": "tests/test_a.py::test_fails",
                        "lineno": 1,
                        "keywords": [],
                        "outcome": "failed",
                        "call": {
                            "duration": 0.001,
                            "outcome": "failed",
                            "longrepr": "assert 0",
                        },
                    },
                    {
                        "nodeid": "tests/test_a.py::test_prints",
                        "lineno": 5,
                        "keywords": [],
                        "outcome": "passed",
                        "call": {
                            "duration": 0.001,
                            "outcome": "passed",
                            "stdout": "HELLO\n",
                        },
                    },
                ],
                "warnings": [],
            }
        )
    )


def _mixed_results(status: RunStatus) -> dict[str, Any]:
    """Build FAILED or ERROR results over the mixed report."""
    report = _mixed_report()
    return make_pytest_results(
        summary={"passed": 1, "failed": 1, "error": 0, "collected": 2},
        test_results=report,
        verdict=RunVerdict(status, ["collection error"], report.exitcode),
        summary_text="1 failed, 1 passed",
    )


def test_format_pytest_result_failed_with_show_output(
    checker_tools: CheckerTools,
) -> None:
    """A failing run with show_output adds passing output after the failure blocks."""
    result = checker_tools._format_pytest_result_with_details(
        _mixed_results(RunStatus.FAILED), show_details=True, show_output=True
    )
    assert "tests/test_a.py::test_fails" in result
    failures = result.index("Pytest found issues that need attention:")
    passing = result.index("\n\nCaptured output of passing tests:")
    assert failures < passing
    assert result.index("assert 0") < passing
    assert "HELLO" in result[passing:]


def test_format_pytest_result_failed_without_show_output(
    checker_tools: CheckerTools,
) -> None:
    """Without show_output, a failing run adds no passing output."""
    result = checker_tools._format_pytest_result_with_details(
        _mixed_results(RunStatus.FAILED), show_details=True
    )
    assert "Captured output of passing tests" not in result
    assert "HELLO" not in result


def test_format_pytest_result_error_with_tests_and_show_output(
    checker_tools: CheckerTools,
) -> None:
    """ERROR with a report that has tests adds passing output after the error details."""
    without = checker_tools._format_pytest_result_with_details(
        _mixed_results(RunStatus.ERROR), show_details=True
    )
    result = checker_tools._format_pytest_result_with_details(
        _mixed_results(RunStatus.ERROR), show_details=True, show_output=True
    )
    assert result.startswith(f"{without}\n\nCaptured output of passing tests:")
    assert "HELLO" in result


def test_format_pytest_result_error_without_tests_ignores_show_output(
    checker_tools: CheckerTools,
) -> None:
    """ERROR whose report has no tests is unchanged by show_output."""
    without = checker_tools._format_pytest_result_with_details(
        _error_results(), show_details=True
    )
    result = checker_tools._format_pytest_result_with_details(
        _error_results(), show_details=True, show_output=True
    )
    assert result == without


def test_format_pytest_result_failed_passes_capture(
    checker_tools: CheckerTools,
) -> None:
    """The capture kinds reach the failure blocks."""
    with patch(
        "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
    ) as mock_prompt:
        mock_prompt.return_value = "Detailed failure info..."
        checker_tools._format_pytest_result_with_details(
            _mixed_results(RunStatus.FAILED),
            show_details=True,
            capture=frozenset({"log"}),
        )
    assert mock_prompt.call_args.kwargs["capture"] == frozenset({"log"})


def test_format_pytest_result_failed_show_output_tight_budget(
    checker_tools: CheckerTools,
) -> None:
    """When the failures leave too little room, the passing output is named as dropped."""
    with patch(
        "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
    ) as mock_prompt:
        mock_prompt.return_value = "\n".join(f"line {i}" for i in range(15))
        result = checker_tools._format_pytest_result_with_details(
            _mixed_results(RunStatus.FAILED),
            show_details=True,
            show_output=True,
            max_lines=20,
        )
    assert result.endswith(f"\n\n{DROPPED_NOTICE} passing-test output (-s)")
    assert "line 14" in result
    assert "HELLO" not in result


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


def _failed_report(collectors: list[Collector] | None = None) -> PytestReport:
    """Build a real FAILED report (exit 1) with only error_message unless given."""
    return PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=1,
        root="/project",
        environment={},
        summary=Summary(collected=2, total=2, passed=1, failed=1),
        collectors=collectors or [],
        tests=[],
        error_context=ErrorContext(
            exit_code=1,
            exit_code_meaning="Tests failed",
            error_message="full pytest output\n1 failed, 1 passed",
            suggestion="",
        ),
    )


def test_format_pytest_result_failed_with_collection_errors(
    checker_tools: CheckerTools,
) -> None:
    """The xdist hint precedes the failure prompt in a FAILED run."""
    report = _failed_report(
        [
            Collector(
                nodeid="tests",
                outcome="failed",
                result=[],
                longrepr=f"{XDIST_MARKER} on gw1",
            )
        ]
    )
    test_results = make_pytest_results(
        summary={"passed": 1, "failed": 1, "collected": 2},
        test_results=report,
        verdict=classify_run(report),
        summary_text="1 failed, 1 passed",
    )
    with patch(
        "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
    ) as mock_prompt:
        mock_prompt.return_value = "Detailed failure info..."
        result = checker_tools._format_pytest_result_with_details(
            test_results, show_details=True
        )
    assert result.startswith("1 failed, 1 passed\n\nCollection problems:\n")
    assert XDIST_HINT in result
    assert result.index(XDIST_HINT) < result.index(
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
        summary_text="1 failed, 1 passed",
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Collection problems:" not in result
    assert result.startswith(
        "1 failed, 1 passed\n\nPytest found issues that need attention:"
    )


def _stopped_results(summary: Summary) -> dict[str, Any]:
    """Build FAILED results over a report with the given summary."""
    report = _failed_report()
    report.summary = summary
    return make_pytest_results(
        summary={"passed": 1, "failed": 1, "collected": summary.collected},
        test_results=report,
        verdict=classify_run(report),
        summary_text="1 failed, 1 passed",
    )


def test_format_pytest_result_failed_leads_with_did_not_run_line(
    checker_tools: CheckerTools,
) -> None:
    """Unrun selected tests are counted directly after the summary text."""
    test_results = _stopped_results(Summary(collected=4, total=2, passed=1, failed=1))
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert result.startswith(
        "1 failed, 1 passed\n2 of 4 selected tests did not run\n\n"
        "Pytest found issues that need attention:"
    )


def test_format_pytest_result_failed_all_ran_has_no_did_not_run_line(
    checker_tools: CheckerTools,
) -> None:
    """When every selected test ran, no did-not-run text appears."""
    test_results = _stopped_results(Summary(collected=2, total=2, passed=1, failed=1))
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "did not run" not in result


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


def test_format_pytest_result_suspicious_collect_only(
    checker_tools: CheckerTools,
) -> None:
    """A collect-only run lists the selected IDs instead of not verified."""
    report = PytestReport(
        created=0.0,
        duration=0.5,
        exitcode=0,
        root="/project",
        environment={},
        summary=Summary(collected=4, total=0, deselected=3),
        collectors=[
            Collector(
                nodeid="tests/test_x.py",
                outcome="passed",
                result=[
                    CollectorResult(nodeid="tests/test_x.py::test_a", type="Function")
                ],
            )
        ],
    )
    test_results = make_pytest_results(
        RunStatus.SUSPICIOUS,
        summary={"collected": 4, "deselected": 3},
        test_results=report,
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True, collect_only=True
    )
    assert result.startswith("Collected")
    assert "tests/test_x.py::test_a" in result
    assert "Not verified" not in result


def test_format_pytest_result_suspicious_subtracts_deselected(
    checker_tools: CheckerTools,
) -> None:
    """Without collect_only, SUSPICIOUS counts only the selected tests."""
    test_results = make_pytest_results(
        RunStatus.SUSPICIOUS,
        summary={"collected": 4, "deselected": 3},
        test_results=None,
    )
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Collected 1 tests" in result
    assert "Not verified" in result


def _error_results() -> dict[str, Any]:
    report = PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=1,
        root="/project",
        environment={},
        summary=Summary(collected=5, total=5, passed=5),
    )
    return make_pytest_results(
        summary={"passed": 5, "collected": 5},
        test_results=report,
        verdict=RunVerdict(RunStatus.ERROR, ["something broke"], 1),
    )


def _failed_results() -> dict[str, Any]:
    report = _failed_report()
    return make_pytest_results(
        summary={"passed": 1, "failed": 1, "collected": 2},
        test_results=report,
        verdict=classify_run(report),
        summary_text="1 failed, 1 passed",
    )


@pytest.mark.parametrize("build", [_failed_results, _error_results])
def test_format_pytest_result_collect_only_ignored_outside_suspicious(
    checker_tools: CheckerTools, build: Any
) -> None:
    """FAILED and ERROR replies are the same with collect_only."""
    without = checker_tools._format_pytest_result_with_details(
        build(), show_details=True
    )
    with_flag = checker_tools._format_pytest_result_with_details(
        build(), show_details=True, collect_only=True
    )
    assert with_flag == without


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


_WARNINGS = " | ⚠️ Warnings: 2"


def _with_warnings(report: PytestReport) -> PytestReport:
    report.warnings = [ReportWarning(message="w1"), ReportWarning(message="w2")]
    return report


def test_format_pytest_result_passed_appends_warnings_count(
    checker_tools: CheckerTools,
) -> None:
    """PASSED appends the warnings count to the summary line."""
    results = _passing_results()
    _with_warnings(results["test_results"])
    result = checker_tools._format_pytest_result_with_details(
        results, show_details=True
    )
    assert result == f"Pytest check completed. 1 passed in 0.10s{_WARNINGS}"


@pytest.mark.parametrize("show_details", [True, False])
def test_format_pytest_result_failed_appends_warnings_count(
    checker_tools: CheckerTools, show_details: bool
) -> None:
    """FAILED appends the warnings count to the summary text, with or without details."""
    results = _failed_results()
    _with_warnings(results["test_results"])
    result = checker_tools._format_pytest_result_with_details(
        results, show_details=show_details
    )
    assert result.splitlines()[0].endswith(f"1 failed, 1 passed{_WARNINGS}")


def test_format_pytest_result_error_appends_warnings_count(
    checker_tools: CheckerTools,
) -> None:
    """ERROR with a report shows the count on its summary line."""
    results = _error_results()
    _with_warnings(results["test_results"])
    result = checker_tools._format_pytest_result_with_details(
        results, show_details=True
    )
    assert result.splitlines()[1].endswith(f"✅ Passed: 5{_WARNINGS}")


def test_format_pytest_result_suspicious_has_no_warnings_count(
    checker_tools: CheckerTools,
) -> None:
    """SUSPICIOUS text is unchanged by warnings."""
    report = _with_warnings(
        PytestReport(
            created=0.0,
            duration=0.1,
            exitcode=0,
            root="/project",
            environment={},
            summary=Summary(collected=5, total=0),
        )
    )
    results = make_pytest_results(
        RunStatus.SUSPICIOUS, summary={"collected": 5}, test_results=report
    )
    result = checker_tools._format_pytest_result_with_details(
        results, show_details=True
    )
    assert "⚠️ Warnings" not in result
