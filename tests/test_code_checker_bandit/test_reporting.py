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
        assert result == (
            "bandit found 0 issues across 0 rules\n\n"
            "File errors (files not scanned):\n"
            "- bad.py: syntax error"
        )

    def test_format_total_line_first(self) -> None:
        msgs = [
            _make_bandit_message(test_id="B101", filename="src/a.py"),
            _make_bandit_message(test_id="B101", filename="tests/b.py"),
            _make_bandit_message(test_id="B105", filename="src/c.py"),
        ]
        result = format_bandit_report(msgs, [], max_issues=1)
        assert result is not None
        assert result.startswith("bandit found 3 issues across 2 rules\n\n")

    def test_format_detail_header_with_name_and_split(self) -> None:
        msgs = [
            _make_bandit_message(filename="tests/a.py"),
            _make_bandit_message(filename="tests/b.py", line_number=3),
            _make_bandit_message(filename="src/c.py"),
        ]
        result = format_bandit_report(msgs, [], max_issues=1)
        assert result is not None
        assert (
            "bandit found 3 issues with B101 assert_used (tests: 2, src: 1) "
            "[severity: LOW, confidence: HIGH]"
        ) in result

    def test_format_detail_header_singular(self) -> None:
        result = format_bandit_report([_make_bandit_message()], [], max_issues=1)
        assert result is not None
        assert (
            "bandit found 1 issue with B101 assert_used (src: 1) "
            "[severity: LOW, confidence: HIGH]"
        ) in result

    def test_format_max_issues_zero_counts_only(self) -> None:
        msgs = [
            _make_bandit_message(
                test_id="B201",
                test_name="flask_debug_true",
                issue_severity="HIGH",
                filename="src/a.py",
            ),
            _make_bandit_message(test_id="B101", filename="tests/b.py"),
            _make_bandit_message(test_id="B101", filename="tests/c.py"),
        ]
        result = format_bandit_report(msgs, [], max_issues=0)
        assert result == (
            "bandit found 3 issues across 2 rules\n\n"
            "- B201 flask_debug_true (HIGH): 1 occurrence (src: 1)\n"
            "- B101 assert_used (LOW): 2 occurrences (tests: 2)"
        )
        assert ".py:" not in result

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
        assert "bandit found 1 issue with B201 assert_used ((root): 1)" in result
        assert "a.py:10" in result

        # Remaining should be summary only
        assert "- B105 assert_used (MEDIUM): 1 occurrence ((root): 1)" in result
        assert "- B101 assert_used (LOW): 1 occurrence ((root): 1)" in result

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

    def test_format_omits_cwe_line_without_id(self) -> None:
        msgs = [_make_bandit_message(cwe_id=0, cwe_link="")]
        result = format_bandit_report(msgs, [], max_issues=1)
        assert result is not None
        assert "CWE-" not in result

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
        total_pos = result.index("bandit found 1 issue across 1 rule")
        bandit_pos = result.index("bandit found 1 issue with")
        assert total_pos < error_pos < bandit_pos
