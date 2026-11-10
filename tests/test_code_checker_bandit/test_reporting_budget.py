"""Budget tests for the bandit report."""

import pytest

from mcp_tools_py.code_checker_bandit.models import BanditMessage
from mcp_tools_py.code_checker_bandit.reporting import format_bandit_report
from mcp_tools_py.utils.report_budget import LOCATION_HINT, SUMMARY_HINT, TOOL_LINES


def _msg(test_id: str, line: int, filename: str, severity: str) -> BanditMessage:
    return BanditMessage(
        test_id=test_id,
        test_name=f"name_{test_id}",
        issue_severity=severity,
        issue_confidence="HIGH",
        issue_text=f"problem {test_id}",
        filename=filename,
        line_number=line,
        more_info="",
        cwe_id=0,
        cwe_link="",
    )


@pytest.mark.parametrize("max_issues", [1, 2])
def test_large_result_stays_within_budget(max_issues: int) -> None:
    """1 rule x 400 locations in 50 files plus 40 other rules: bounded."""
    messages = [_msg("B101", i, f"src/f{i % 50}.py", "HIGH") for i in range(400)]
    for r in range(40):
        messages += [_msg(f"B{200 + r}", n, f"src/m{n}.py", "LOW") for n in range(3)]

    report = format_bandit_report(messages, [], max_issues=max_issues)
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
