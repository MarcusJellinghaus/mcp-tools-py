"""Unit tests for the deptry reporting module."""

from mcp_tools_py.code_checker_deptry.reporting import (
    MAX_LOCATIONS_PER_ISSUE,
    _location,
    format_deptry_report,
)
from mcp_tools_py.code_checker_deptry.runners import DeptryMessage

_DEP001_TEXT = "'yaml' imported but missing from the dependency definitions"


def _dep001(file: str = "src/a.py", line: int = 3) -> DeptryMessage:
    """Build a DEP001 message with a source location."""
    return DeptryMessage(
        code="DEP001",
        message=_DEP001_TEXT,
        module="yaml",
        file=file,
        line=line,
        column=1,
    )


def _dep002(module: str = "requests") -> DeptryMessage:
    """Build a DEP002 message located in pyproject.toml."""
    return DeptryMessage(
        code="DEP002",
        message=f"'{module}' defined as a dependency but not used in the codebase",
        module=module,
        file="pyproject.toml",
        line=None,
        column=None,
    )


class TestLocation:
    """Test cases for _location."""

    def test_source_location(self) -> None:
        assert _location(_dep001()) == f"- src/a.py:3:1 yaml {_DEP001_TEXT}"

    def test_dep002_location(self) -> None:
        assert _location(_dep002()) == "- pyproject.toml: 'requests'"


class TestFormatDeptryReport:
    """Test cases for format_deptry_report."""

    def test_empty_returns_none(self) -> None:
        assert format_deptry_report([]) is None

    def test_total_line(self) -> None:
        report = format_deptry_report([_dep001(), _dep001("src/b.py"), _dep002()])
        assert report is not None
        assert report.split("\n\n")[0] == "deptry found 3 issues across 2 rules"

    def test_most_frequent_code_detailed_first(self) -> None:
        report = format_deptry_report(
            [_dep002("a"), _dep002("b"), _dep001()], max_issues=1
        )
        assert report is not None
        sections = report.split("\n\n")
        assert sections[1].startswith(
            "deptry found 2 issues with rule DEP002 ((root): 2)."
        )
        assert sections[2] == "- DEP001: 1 occurrence (src: 1)"

    def test_ties_broken_by_code(self) -> None:
        report = format_deptry_report([_dep002(), _dep001()], max_issues=1)
        assert report is not None
        sections = report.split("\n\n")
        assert "with rule DEP001" in sections[1]
        assert sections[2] == "- DEP002: 1 occurrence ((root): 1)"

    def test_detail_section(self) -> None:
        report = format_deptry_report(
            [_dep001(), _dep001("src/b.py", 7), _dep002()], max_issues=2
        )
        assert report is not None
        sections = report.split("\n\n")
        assert sections[1] == "\n".join(
            [
                "deptry found 2 issues with rule DEP001 (src: 2).",
                "Locations:",
                f"- src/a.py:3:1 yaml {_DEP001_TEXT}",
                f"- src/b.py:7:1 yaml {_DEP001_TEXT}",
            ]
        )
        assert sections[2] == "\n".join(
            [
                "deptry found 1 issue with rule DEP002 ((root): 1).",
                "Locations:",
                "- pyproject.toml: 'requests'",
            ]
        )

    def test_max_issues_zero_counts_only(self) -> None:
        report = format_deptry_report(
            [_dep001(), _dep001("src/b.py"), _dep002()], max_issues=0
        )
        assert report == (
            "deptry found 3 issues across 2 rules\n\n"
            "- DEP001: 2 occurrences (src: 2)\n"
            "- DEP002: 1 occurrence ((root): 1)"
        )
        assert "src/a.py" not in report
        assert "pyproject.toml" not in report

    def test_negative_max_issues_treated_as_zero(self) -> None:
        report = format_deptry_report([_dep001()], max_issues=-3)
        assert report == (
            "deptry found 1 issue across 1 rule\n\n- DEP001: 1 occurrence (src: 1)"
        )

    def test_max_issues_larger_than_groups_details_all(self) -> None:
        report = format_deptry_report([_dep001(), _dep002()], max_issues=10)
        assert report is not None
        sections = report.split("\n\n")
        assert len(sections) == 3
        assert all("Locations:" in section for section in sections[1:])

    def test_overflow_line(self) -> None:
        count = MAX_LOCATIONS_PER_ISSUE + 5
        messages = [_dep001(line=i + 1) for i in range(count)]
        report = format_deptry_report(messages)
        assert report is not None
        lines = report.splitlines()
        location_lines = [line for line in lines if line.startswith("- src/a.py:")]
        assert len(location_lines) == MAX_LOCATIONS_PER_ISSUE
        assert lines[-1] == "... and 5 more occurrences"
