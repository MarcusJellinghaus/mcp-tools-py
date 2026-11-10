"""Budget tests for the ruff fix report."""

from mcp_tools_py.code_checker_ruff.reporting import (
    FILES_HINT,
    FIX_HINT,
    format_ruff_fix_report,
)
from mcp_tools_py.utils.report_budget import SUMMARY_TOP, TOOL_LINES
from mcp_tools_py.utils.ruff_parsing import RuffMessage


def _message(code: str, filename: str = "src/foo.py") -> RuffMessage:
    return RuffMessage(
        code=code,
        message="msg",
        filename=filename,
        line=1,
        column=0,
        end_line=1,
        end_column=0,
        url=f"https://docs.astral.sh/ruff/rules/rule-{code.lower()}",
        fixable=False,
        noqa_row=1,
    )


def _changed(count: int) -> list[str]:
    return [f"src/file_{i}.py" for i in range(count)]


def _remaining(rules: int) -> list[RuffMessage]:
    return [_message(f"E{100 + i}") for i in range(rules) for _ in range(i + 1)]


def test_large_fix_report_stays_within_budget() -> None:
    report = format_ruff_fix_report(_changed(500), _remaining(60))

    lines = report.splitlines()
    assert len(lines) < TOOL_LINES
    assert f"... and {500 - SUMMARY_TOP} more files" in report
    assert lines[-1] == FIX_HINT


def test_file_overflow_carries_files_hint() -> None:
    report = format_ruff_fix_report(_changed(500), _remaining(5))

    overflow = [line for line in report.splitlines() if "more files" in line]
    assert overflow == [f"... and {500 - SUMMARY_TOP} more files — {FILES_HINT}"]
    assert FIX_HINT not in report
    assert "more rules" not in report


def test_small_fix_report_lists_every_file() -> None:
    changed = _changed(3)
    report = format_ruff_fix_report(changed, [])

    assert report.splitlines()[0] == "Ruff applied fixes to 3 files (src: 3):"
    for path in changed:
        assert f"- {path}" in report
    assert FILES_HINT not in report
    assert FIX_HINT not in report


def test_no_changed_files_has_no_split() -> None:
    report = format_ruff_fix_report([], [])

    assert report == "Ruff applied fixes to 0 files:"
