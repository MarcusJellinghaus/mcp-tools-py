"""Tests for the exit-5 skip block in CheckerTools' pytest result formatting."""

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_pytest.models import Collector, PytestReport, Summary
from mcp_tools_py.code_checker_pytest.reporting import DROPPED_NOTICE
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.utils.tool_context import ToolContext
from tests._pytest_results import make_pytest_results

_NO_TESTS = "No Tests Found: Pytest did not find any tests to run."


@pytest.fixture
def checker_tools(tool_context: ToolContext) -> CheckerTools:
    """Create a CheckerTools instance over the shared context."""
    return CheckerTools(tool_context)


def _skip_report(count: int, distinct: bool = False) -> PytestReport:
    """An exit-5 report with `count` module-skipped collectors."""
    collectors = [
        Collector(
            nodeid=f"tests/test_{i}.py",
            outcome="skipped",
            result=[],
            longrepr=str(
                (
                    f"/project/tests/test_{i}.py",
                    3,
                    f"Skipped: no db {i}" if distinct else "Skipped: no db",
                )
            ),
        )
        for i in range(count)
    ]
    return PytestReport(
        created=0.0,
        duration=0.1,
        exitcode=5,
        root="/project",
        environment={},
        summary=Summary(collected=0, total=0),
        collectors=collectors,
    )


def test_format_pytest_result_exit5_skip_block(checker_tools: CheckerTools) -> None:
    """Exit 5 with a skip_report appends the skip block after the error text."""
    without = checker_tools._format_pytest_result_with_details(
        make_pytest_results(RunStatus.ERROR, [_NO_TESTS], skip_report=None),
        show_details=True,
    )
    result = checker_tools._format_pytest_result_with_details(
        make_pytest_results(RunStatus.ERROR, [_NO_TESTS], skip_report=_skip_report(2)),
        show_details=True,
    )
    assert result == (
        f"{without}\n⏭️ Skipped: 2\n"
        "SKIPPED [1] tests/test_0.py:3: no db\n"
        "SKIPPED [1] tests/test_1.py:3: no db"
    )
    assert result.index("Problems:") < result.index(_NO_TESTS)
    assert result.index(_NO_TESTS) < result.index("⏭️ Skipped: 2")


def test_format_pytest_result_error_without_skip_report(
    checker_tools: CheckerTools,
) -> None:
    """Without a skip_report, or with nothing skipped, the error text is unchanged."""
    plain = checker_tools._format_pytest_result_with_details(
        make_pytest_results(RunStatus.ERROR, [_NO_TESTS]), show_details=True
    )
    empty = checker_tools._format_pytest_result_with_details(
        make_pytest_results(RunStatus.ERROR, [_NO_TESTS], skip_report=_skip_report(0)),
        show_details=True,
    )
    assert "Skipped" not in plain
    assert empty == plain


def test_format_pytest_result_exit5_skip_block_budget(
    checker_tools: CheckerTools,
) -> None:
    """Skip reasons past the budget are named in the notice; the reply stays within it."""
    max_lines, max_chars = 15, 1500
    result = checker_tools._format_pytest_result_with_details(
        make_pytest_results(
            RunStatus.ERROR, [_NO_TESTS], skip_report=_skip_report(60, distinct=True)
        ),
        show_details=True,
        max_lines=max_lines,
        max_chars=max_chars,
    )
    lines = result.splitlines()
    assert len(lines) <= max_lines
    assert len(result) <= max_chars
    assert "⏭️ Skipped: 60" in lines
    assert lines[-1] == f"{DROPPED_NOTICE} skip reasons"
