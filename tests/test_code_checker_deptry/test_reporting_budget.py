"""Budget tests for the deptry report."""

import pytest

from mcp_tools_py.code_checker_deptry.reporting import format_deptry_report
from mcp_tools_py.code_checker_deptry.runners import DeptryMessage
from mcp_tools_py.utils.report_budget import LOCATION_HINT, SUMMARY_HINT, TOOL_LINES


def _msg(code: str, line: int, file: str) -> DeptryMessage:
    return DeptryMessage(
        code=code,
        message="'yaml' imported but missing from the dependency definitions",
        module="yaml",
        file=file,
        line=line,
        column=1,
    )


@pytest.mark.parametrize("max_issues", [1, 2])
def test_large_result_stays_within_budget(max_issues: int) -> None:
    """1 rule x 400 locations in 50 files plus 40 other rules: bounded."""
    messages = [_msg("DEP001", i, f"src/f{i % 50}.py") for i in range(400)]
    for r in range(40):
        messages += [_msg(f"DEP{100 + r}", n, f"src/m{n}.py") for n in range(3)]

    report = format_deptry_report(messages, max_issues=max_issues)
    assert report is not None
    lines = report.splitlines()
    assert len(lines) < TOOL_LINES
    assert lines[-1] == SUMMARY_HINT
    hidden = 41 - max_issues
    assert (
        f"--- {hidden} additional rules found ({hidden * 3} occurrences) ---" in report
    )
    overflow = [line for line in lines if line.startswith("... and 320 more")]
    assert len(overflow) == 1
    assert LOCATION_HINT in overflow[0]
