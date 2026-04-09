"""Unit tests for ruff reporting module."""

from mcp_tools_py.code_checker_ruff.models import RuffMessage
from mcp_tools_py.code_checker_ruff.reporting import (
    MAX_LOCATIONS_PER_ISSUE,
    format_ruff_check_report,
    format_ruff_fix_report,
    get_rule_prefix,
    group_and_sort_issues,
)


def _make_ruff_message(
    code: str = "D100",
    message: str = "Missing docstring in public module",
    filename: str = "src/foo.py",
    line: int = 1,
    column: int = 0,
    end_line: int = 1,
    end_column: int = 0,
    url: str = "https://docs.astral.sh/ruff/rules/undocumented-public-module",
    fixable: bool = False,
    noqa_row: int = 1,
) -> RuffMessage:
    """Build a RuffMessage with sensible defaults."""
    return RuffMessage(
        code=code,
        message=message,
        filename=filename,
        line=line,
        column=column,
        end_line=end_line,
        end_column=end_column,
        url=url,
        fixable=fixable,
        noqa_row=noqa_row,
    )


class TestGetRulePrefix:
    """Test cases for get_rule_prefix."""

    def test_single_letter_prefix(self) -> None:
        assert get_rule_prefix("E501") == "E"

    def test_multi_letter_prefix(self) -> None:
        assert get_rule_prefix("DOC201") == "DOC"

    def test_d_prefix(self) -> None:
        assert get_rule_prefix("D100") == "D"

    def test_w_prefix(self) -> None:
        assert get_rule_prefix("W291") == "W"

    def test_f_prefix(self) -> None:
        assert get_rule_prefix("F401") == "F"


class TestGroupAndSortIssues:
    """Test cases for group_and_sort_issues."""

    def test_empty_list(self) -> None:
        assert group_and_sort_issues([]) == []

    def test_single_code(self) -> None:
        msgs = [
            _make_ruff_message(code="D100", filename="a.py"),
            _make_ruff_message(code="D100", filename="b.py"),
        ]
        groups = group_and_sort_issues(msgs)
        assert len(groups) == 1
        assert groups[0].code == "D100"
        assert len(groups[0].messages) == 2

    def test_sorted_by_prefix_priority(self) -> None:
        """E before W before D."""
        msgs = [
            _make_ruff_message(code="D100"),
            _make_ruff_message(code="W291"),
            _make_ruff_message(code="E501"),
        ]
        groups = group_and_sort_issues(msgs)
        codes = [g.code for g in groups]
        assert codes == ["E501", "W291", "D100"]

    def test_sorted_by_frequency_within_prefix(self) -> None:
        """Same prefix, more frequent first."""
        msgs = [
            _make_ruff_message(code="E501"),
            _make_ruff_message(code="E401"),
            _make_ruff_message(code="E401"),
            _make_ruff_message(code="E401"),
        ]
        groups = group_and_sort_issues(msgs)
        assert groups[0].code == "E401"
        assert groups[1].code == "E501"
        assert len(groups[0].messages) == 3
        assert len(groups[1].messages) == 1


class TestFormatRuffCheckReport:
    """Test cases for format_ruff_check_report."""

    def test_no_issues_returns_none(self) -> None:
        assert format_ruff_check_report([]) is None

    def test_max_issues_1_with_three_rule_types(self) -> None:
        msgs = [
            _make_ruff_message(code="E501", filename="a.py", line=10, column=89),
            _make_ruff_message(code="W291", filename="b.py", line=5, column=0),
            _make_ruff_message(code="D100", filename="c.py", line=1, column=0),
        ]
        result = format_ruff_check_report(msgs, max_issues=1)
        assert result is not None

        # First group (E501) should be detailed
        assert "ruff found 1 issues with rule E501" in result
        assert "a.py:10:89" in result

        # Remaining should be summary only
        assert "- W291: 1 occurrences" in result
        assert "- D100: 1 occurrences" in result

        # No detailed locations for remaining
        assert "b.py:5:0" not in result

    def test_locations_capped(self) -> None:
        """More than MAX_LOCATIONS_PER_ISSUE locations should be capped."""
        count = MAX_LOCATIONS_PER_ISSUE + 10
        msgs = [
            _make_ruff_message(code="E501", filename=f"file{i}.py", line=i)
            for i in range(count)
        ]
        result = format_ruff_check_report(msgs, max_issues=1)
        assert result is not None
        assert f"... and 10 more occurrences" in result

        # Only MAX_LOCATIONS_PER_ISSUE locations should appear
        location_lines = [
            line for line in result.split("\n") if line.startswith("- file")
        ]
        assert len(location_lines) == MAX_LOCATIONS_PER_ISSUE


class TestFormatRuffFixReport:
    """Test cases for format_ruff_fix_report."""

    def test_with_remaining(self) -> None:
        changed = ["src/a.py", "src/b.py"]
        remaining = [
            _make_ruff_message(code="E501", filename="src/a.py"),
            _make_ruff_message(code="E501", filename="src/c.py"),
            _make_ruff_message(code="D100", filename="src/d.py"),
        ]
        result = format_ruff_fix_report(changed, remaining)

        assert "Ruff applied fixes to 2 files:" in result
        assert "- src/a.py" in result
        assert "- src/b.py" in result
        assert "3 remaining issues (2 rule types) not auto-fixable:" in result
        assert "- E501: 2 occurrences" in result
        assert "- D100: 1 occurrences" in result

    def test_no_remaining(self) -> None:
        changed = ["src/a.py"]
        result = format_ruff_fix_report(changed, [])

        assert "Ruff applied fixes to 1 files:" in result
        assert "- src/a.py" in result
        assert "remaining" not in result
