"""Budget tests for the ruff check report."""

from mcp_tools_py.code_checker_ruff.reporting import format_ruff_check_report
from mcp_tools_py.utils.report_budget import SUMMARY_HINT, TOOL_LINES
from mcp_tools_py.utils.ruff_parsing import RuffMessage


def _msg(code: str, line: int, filename: str, message: str = "") -> RuffMessage:
    return RuffMessage(
        code=code,
        message=message or f"problem {code}",
        filename=filename,
        line=line,
        column=1,
        end_line=line,
        end_column=2,
        url="",
        fixable=False,
        noqa_row=line,
    )


def test_large_result_stays_within_budget() -> None:
    """8000 hits across 150 rules, big rules sorted last: bounded, largest named."""
    messages = [_msg("S101", i, f"tests/t{i % 90}.py") for i in range(3444)]
    messages += [_msg("COM812", i, f"src/c{i % 40}.py") for i in range(1037)]
    prefixes = ["E", "W", "F"]
    for r in range(148):
        count = 24 if r < 115 else 23
        code = f"{prefixes[r % 3]}{100 + r}"
        messages += [_msg(code, n, f"src/m{n % 30}.py") for n in range(count)]
    assert len(messages) == 8000

    report = format_ruff_check_report(messages, max_issues=2)
    assert report is not None
    lines = report.splitlines()
    assert len(lines) < TOOL_LINES
    assert lines[0] == "ruff found 8000 issues across 150 rules"
    assert "--- 148 additional rules" in report
    assert "largest: S101 3444, COM812 1037" in report
    assert lines[-1] == SUMMARY_HINT


def test_each_location_keeps_its_own_message() -> None:
    """Two E712 hits with different texts show both texts."""
    messages = [
        _msg("E712", 3, "src/a.py", "Avoid equality comparisons to `True`"),
        _msg("E712", 9, "src/a.py", "Avoid equality comparisons to `False`"),
    ]
    report = format_ruff_check_report(messages)
    assert report is not None
    assert "- src/a.py: 3 — Avoid equality comparisons to `True`" in report
    assert "- src/a.py: 9 — Avoid equality comparisons to `False`" in report
