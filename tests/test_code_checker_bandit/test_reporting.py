"""Unit tests for bandit reporting module."""

from mcp_tools_py.code_checker_bandit.models import BanditMessage
from mcp_tools_py.code_checker_bandit.reporting import (
    MAX_LOCATIONS_PER_ISSUE,
    format_bandit_report,
    group_and_sort_issues,
)


def _make_bandit_message(
    test_id: str = "B101",
    test_name: str = "assert_used",
    issue_severity: str = "LOW",
    issue_confidence: str = "HIGH",
    issue_text: str = "Use of assert detected.",
    filename: str = "src/foo.py",
    line_number: int = 10,
    more_info: str = "https://bandit.readthedocs.io/en/latest/plugins/b101_assert_used.html",
    cwe_id: int = 703,
    cwe_link: str = "https://cwe.mitre.org/data/definitions/703.html",
) -> BanditMessage:
    """Build a BanditMessage with sensible defaults."""
    return BanditMessage(
        test_id=test_id,
        test_name=test_name,
        issue_severity=issue_severity,
        issue_confidence=issue_confidence,
        issue_text=issue_text,
        filename=filename,
        line_number=line_number,
        more_info=more_info,
        cwe_id=cwe_id,
        cwe_link=cwe_link,
    )


class TestGroupAndSortIssues:
    """Test cases for group_and_sort_issues."""

    def test_group_and_sort_empty(self) -> None:
        assert group_and_sort_issues([]) == []

    def test_group_and_sort_by_severity(self) -> None:
        """HIGH before MEDIUM before LOW."""
        msgs = [
            _make_bandit_message(test_id="B101", issue_severity="LOW"),
            _make_bandit_message(test_id="B105", issue_severity="MEDIUM"),
            _make_bandit_message(test_id="B201", issue_severity="HIGH"),
        ]
        groups = group_and_sort_issues(msgs)
        severities = [g.messages[0].issue_severity for g in groups]
        assert severities == ["HIGH", "MEDIUM", "LOW"]

    def test_group_and_sort_by_confidence_tiebreak(self) -> None:
        """Same severity -> HIGH confidence first."""
        msgs = [
            _make_bandit_message(
                test_id="B101", issue_severity="MEDIUM", issue_confidence="LOW"
            ),
            _make_bandit_message(
                test_id="B105", issue_severity="MEDIUM", issue_confidence="HIGH"
            ),
        ]
        groups = group_and_sort_issues(msgs)
        assert groups[0].test_id == "B105"
        assert groups[1].test_id == "B101"

    def test_group_and_sort_by_frequency_tiebreak(self) -> None:
        """Same severity+confidence -> more frequent first."""
        msgs = [
            _make_bandit_message(
                test_id="B101", issue_severity="LOW", issue_confidence="HIGH"
            ),
            _make_bandit_message(
                test_id="B105",
                issue_severity="LOW",
                issue_confidence="HIGH",
                filename="a.py",
            ),
            _make_bandit_message(
                test_id="B105",
                issue_severity="LOW",
                issue_confidence="HIGH",
                filename="b.py",
            ),
        ]
        groups = group_and_sort_issues(msgs)
        assert groups[0].test_id == "B105"
        assert len(groups[0].messages) == 2
        assert groups[1].test_id == "B101"
        assert len(groups[1].messages) == 1


class TestFormatBanditReport:
    """Test cases for format_bandit_report."""

    def test_format_no_issues_returns_none(self) -> None:
        assert format_bandit_report([], []) is None

    def test_format_errors_only(self) -> None:
        result = format_bandit_report([], ["bad.py: syntax error"])
        assert result is not None
        assert "File errors (files not scanned):" in result
        assert "- bad.py: syntax error" in result

    def test_format_max_issues_detail_and_summary(self) -> None:
        """3 groups, max_issues=1 -> 1 detailed + 2 summary."""
        msgs = [
            _make_bandit_message(
                test_id="B201", issue_severity="HIGH", filename="a.py"
            ),
            _make_bandit_message(
                test_id="B105", issue_severity="MEDIUM", filename="b.py"
            ),
            _make_bandit_message(test_id="B101", issue_severity="LOW", filename="c.py"),
        ]
        result = format_bandit_report(msgs, [], max_issues=1)
        assert result is not None

        # First group (HIGH severity B201) should be detailed
        assert "bandit found 1 issues with B201" in result
        assert "a.py:10" in result

        # Remaining should be summary only
        assert "- B105 (MEDIUM): 1 occurrences" in result
        assert "- B101 (LOW): 1 occurrences" in result

        # No detailed locations for remaining
        assert "b.py:" not in result

    def test_format_includes_cwe_reference(self) -> None:
        msgs = [
            _make_bandit_message(
                cwe_id=703, cwe_link="https://cwe.mitre.org/data/definitions/703.html"
            ),
        ]
        result = format_bandit_report(msgs, [], max_issues=1)
        assert result is not None
        assert "CWE-703" in result
        assert "https://cwe.mitre.org/data/definitions/703.html" in result

    def test_format_locations_capped(self) -> None:
        """>50 locations -> capped with '... and N more'."""
        count = MAX_LOCATIONS_PER_ISSUE + 10
        msgs = [
            _make_bandit_message(test_id="B101", filename=f"file{i}.py", line_number=i)
            for i in range(count)
        ]
        result = format_bandit_report(msgs, [], max_issues=1)
        assert result is not None
        assert "... and 10 more occurrences" in result

        location_lines = [
            line for line in result.split("\n") if line.startswith("- file")
        ]
        assert len(location_lines) == MAX_LOCATIONS_PER_ISSUE

    def test_format_errors_at_top(self) -> None:
        """Errors section appears before findings."""
        msgs = [_make_bandit_message()]
        errors = ["bad.py: syntax error"]
        result = format_bandit_report(msgs, errors, max_issues=1)
        assert result is not None

        error_pos = result.index("File errors")
        bandit_pos = result.index("bandit found")
        assert error_pos < bandit_pos
