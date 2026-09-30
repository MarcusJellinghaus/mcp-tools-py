"""Unit tests for ruff reporting module."""

from mcp_tools_py.code_checker_ruff.reporting import (
    MAX_LOCATIONS_PER_ISSUE,
    _rule_label,
    format_ruff_check_report,
    format_ruff_fix_report,
    get_rule_prefix,
    group_and_sort_issues,
)
from mcp_tools_py.utils.ruff_parsing import RuffMessage


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

        assert result.split("\n")[0] == "ruff found 3 issues across 3 rules"

        # First group (E501) should be detailed
        assert (
            "ruff found 1 issue with rule E501 undocumented-public-module "
            "((root): 1)." in result
        )
        assert "a.py:10:89" in result

        # Remaining should be summary only
        assert "- W291 undocumented-public-module: 1 occurrence ((root): 1)" in result
        assert "- D100 undocumented-public-module: 1 occurrence ((root): 1)" in result

        # No detailed locations for remaining
        assert "b.py:5:0" not in result

    def test_total_line_singular(self) -> None:
        result = format_ruff_check_report([_make_ruff_message()])
        assert result is not None
        assert result.split("\n")[0] == "ruff found 1 issue across 1 rule"

    def test_max_issues_0_counts_only(self) -> None:
        msgs = [
            _make_ruff_message(
                code="SIM117",
                filename="tests/a.py",
                line=3,
                column=5,
                url="https://docs.astral.sh/ruff/rules/multiple-with-statements",
            ),
            _make_ruff_message(
                code="SIM102",
                filename="src/b.py",
                line=7,
                column=1,
                url="https://docs.astral.sh/ruff/rules/collapsible-if",
            ),
            _make_ruff_message(
                code="SIM102",
                filename="tests/c.py",
                line=8,
                column=2,
                url="https://docs.astral.sh/ruff/rules/collapsible-if",
            ),
        ]
        result = format_ruff_check_report(msgs, max_issues=0)
        assert result == (
            "ruff found 3 issues across 2 rules\n"
            "\n"
            "- SIM102 collapsible-if: 2 occurrences (src: 1, tests: 1)\n"
            "- SIM117 multiple-with-statements: 1 occurrence (tests: 1)"
        )

    def test_detail_header_shows_name_and_split_not_url(self) -> None:
        msgs = [
            _make_ruff_message(code="E501", filename="src/a.py"),
            _make_ruff_message(code="E501", filename="src/b.py"),
            _make_ruff_message(code="E501", filename="tests/c.py"),
        ]
        result = format_ruff_check_report(msgs, max_issues=1)
        assert result is not None
        assert (
            "ruff found 3 issues with rule E501 undocumented-public-module "
            "(src: 2, tests: 1)." in result
        )
        assert "https://" not in result

    def test_empty_url_shows_code_only(self) -> None:
        msgs = [_make_ruff_message(code="invalid-syntax", url="")]
        result = format_ruff_check_report(msgs, max_issues=1)
        assert result is not None
        assert "ruff found 1 issue with rule invalid-syntax (src: 1)." in result

    def test_outside_path_in_split(self) -> None:
        msgs = [_make_ruff_message(filename="D:\\other\\x.py")]
        result = format_ruff_check_report(msgs, max_issues=0)
        assert result is not None
        assert "((outside): 1)" in result

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


class TestRuleLabel:
    """Test cases for _rule_label."""

    def test_name_from_url(self) -> None:
        assert (
            _rule_label("SIM102", "https://docs.astral.sh/ruff/rules/collapsible-if")
            == "SIM102 collapsible-if"
        )

    def test_trailing_slash(self) -> None:
        assert (
            _rule_label("SIM102", "https://docs.astral.sh/ruff/rules/collapsible-if/")
            == "SIM102 collapsible-if"
        )

    def test_none_url(self) -> None:
        assert _rule_label("invalid-syntax", None) == "invalid-syntax"

    def test_empty_url(self) -> None:
        assert _rule_label("invalid-syntax", "") == "invalid-syntax"


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
