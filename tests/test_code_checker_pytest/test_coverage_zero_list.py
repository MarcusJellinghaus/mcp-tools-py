"""Tests for the digest's zero-coverage list."""

from typing import Any

import pytest

from mcp_tools_py.code_checker_pytest.coverage import (
    MAX_ZERO_COVERAGE_ROWS,
    _zero_coverage_rows,
    format_coverage_digest,
)
from tests.test_code_checker_pytest._coverage_report import _SELECTION, _file, _report


def _uncovered(stmts: int) -> dict[str, Any]:
    """One file entry with nothing covered."""
    return _file(stmts, list(range(1, stmts + 1)))


def _covered() -> dict[str, Any]:
    """One file entry with a covered statement and a gap."""
    return _file(10, [1], {"f": [1]})


class TestZeroCoverageList:
    """Test the collapsed list of modules with nothing covered."""

    def test_uncovered_directory_is_one_row(self) -> None:
        """A fully uncovered directory is one row, with summed statements."""
        files = {
            "src/pkg/a/m.py": _covered(),
            "src/pkg/b/x.py": _uncovered(3),
            "src/pkg/b/y.py": _uncovered(4),
        }

        assert _zero_coverage_rows(files) == [("src/pkg/b/", 7)]

        digest = format_coverage_digest(_report(files), _SELECTION)
        assert "2 modules have no covered statements in this selection:" in digest
        assert "    src/pkg/b/ (7 missing statements)" in digest
        assert "x.py" not in digest

    def test_directory_with_a_covered_file_does_not_collapse(self) -> None:
        """The zero files next to a covered file are listed individually."""
        files = {
            "src/pkg/a/m.py": _covered(),
            "src/pkg/a/x.py": _uncovered(3),
            "src/pkg/a/y.py": _uncovered(2),
            "src/pkg/b/n.py": _covered(),
        }

        assert _zero_coverage_rows(files) == [
            ("src/pkg/a/x.py", 3),
            ("src/pkg/a/y.py", 2),
        ]

    def test_covered_init_stops_the_collapse(self) -> None:
        """A directory whose __init__.py has covered statements doesn't collapse."""
        files = {
            "src/pkg/a/__init__.py": _file(2, [1]),
            "src/pkg/a/x.py": _uncovered(3),
            "src/pkg/a/y.py": _uncovered(2),
            "src/pkg/b/n.py": _covered(),
        }

        assert _zero_coverage_rows(files) == [
            ("src/pkg/a/x.py", 3),
            ("src/pkg/a/y.py", 2),
        ]

    def test_empty_init_does_not_stop_the_collapse(self) -> None:
        """A 0-statement __init__.py neither blocks nor counts."""
        files = {
            "src/pkg/a/__init__.py": _file(0, []),
            "src/pkg/a/x.py": _uncovered(3),
            "src/pkg/b/n.py": _covered(),
        }

        assert _zero_coverage_rows(files) == [("src/pkg/a/", 3)]

        digest = format_coverage_digest(_report(files), _SELECTION)
        assert "1 modules have no covered statements" in digest

    def test_nested_directory_collapses_to_top_most_uncovered(self) -> None:
        """The row is the highest ancestor without a covered file."""
        files = {
            "src/pkg/a/m.py": _covered(),
            "src/pkg/a/b/y.py": _uncovered(2),
            "src/pkg/a/b/c/x.py": _uncovered(3),
            "src/pkg/z/n.py": _covered(),
        }

        assert _zero_coverage_rows(files) == [("src/pkg/a/b/", 5)]

    def test_uncovered_tree_collapses_to_the_common_prefix(self) -> None:
        """Nothing covered at all gives the common prefix, not an ancestor of it."""
        files = {"src/pkg/a/x.py": _uncovered(3), "src/pkg/b/y.py": _uncovered(2)}

        assert _zero_coverage_rows(files) == [("src/pkg/", 5)]

    def test_project_root_is_never_a_row(self) -> None:
        """With no common prefix each top-level directory gets a row."""
        files = {
            "a/x.py": _uncovered(3),
            "b/y.py": _uncovered(2),
            "z.py": _uncovered(1),
        }

        assert _zero_coverage_rows(files) == [("a/", 3), ("b/", 2), ("z.py", 1)]

    @pytest.mark.parametrize("root", ["/", "C:/"], ids=["posix", "drive"])
    def test_filesystem_root_is_never_a_row(self, root: str) -> None:
        """Paths outside the project collapse no further than below the root."""
        files = {
            f"{root}x/m.py": _uncovered(3),
            f"{root}y/n.py": _uncovered(2),
            "src/k.py": _uncovered(1),
        }

        assert _zero_coverage_rows(files) == [
            (f"{root}x/", 3),
            (f"{root}y/", 2),
            ("src/", 1),
        ]

    def test_file_outside_the_prefix_gets_its_own_row(self) -> None:
        """An __init__.py above the prefix doesn't join the prefix's row."""
        files = {
            "src/__init__.py": _uncovered(1),
            "src/pkg/a/x.py": _uncovered(3),
            "src/pkg/b/y.py": _uncovered(2),
        }

        assert _zero_coverage_rows(files) == [
            ("src/pkg/", 5),
            ("src/__init__.py", 1),
        ]

    def test_windows_keys_give_normalized_labels(self) -> None:
        """Backslash keys group like forward-slash keys and print normalized."""
        files = {
            "src\\pkg\\a\\m.py": _covered(),
            "src\\pkg\\a\\x.py": _uncovered(3),
            "src\\pkg\\b\\y.py": _uncovered(2),
        }

        assert _zero_coverage_rows(files) == [
            ("src/pkg/a/x.py", 3),
            ("src/pkg/b/", 2),
        ]

    def test_rows_are_sorted_by_missing_statements(self) -> None:
        """More missing statements come first; ties go by label."""
        files = {
            "src/m.py": _covered(),
            "src/b/x.py": _uncovered(2),
            "src/c/x.py": _uncovered(9),
            "src/a/x.py": _uncovered(2),
        }

        assert _zero_coverage_rows(files) == [
            ("src/c/", 9),
            ("src/a/", 2),
            ("src/b/", 2),
        ]

    def test_rows_are_capped_and_the_header_counts_modules(self) -> None:
        """The tail line counts rows; the header still counts modules."""
        files: dict[str, Any] = {"src/m.py": _covered()}
        for i in range(20):
            files[f"src/d{i:02}/x.py"] = _uncovered(100 - i)
            files[f"src/d{i:02}/y.py"] = _uncovered(1)

        lines = format_coverage_digest(_report(files), _SELECTION).splitlines()

        start = lines.index("40 modules have no covered statements in this selection:")
        assert lines[start + 1] == "    src/d00/ (101 missing statements)"
        assert lines[start + MAX_ZERO_COVERAGE_ROWS] == (
            "    src/d14/ (87 missing statements)"
        )
        assert lines[start + MAX_ZERO_COVERAGE_ROWS + 1] == "    … and 5 more"
        assert MAX_ZERO_COVERAGE_ROWS == 15

    def test_exactly_the_cap_has_no_tail_line(self) -> None:
        """A list that fits has no tail line."""
        files: dict[str, Any] = {"src/m.py": _covered()}
        for i in range(MAX_ZERO_COVERAGE_ROWS):
            files[f"src/d{i:02}/x.py"] = _uncovered(1)

        assert "… and" not in format_coverage_digest(_report(files), _SELECTION)

    def test_no_cause_is_attributed(self) -> None:
        """The list says nothing about why a module has no coverage."""
        files = {"src/a/x.py": _uncovered(3), "src/b/m.py": _covered()}

        digest = format_coverage_digest(_report(files), _SELECTION)

        for cause in ("untested", "not selected", "never traced"):
            assert cause not in digest

    def test_large_project_overview_stays_short(self) -> None:
        """250 modules over 12 packages at max_modules=0 fit in 40 lines."""
        files = {
            f"src/pkg/p{i % 12:02}/m{i:03}.py": (
                _covered() if i % 12 >= 6 and i % 5 == 0 else _uncovered(10)
            )
            for i in range(250)
        }

        digest = format_coverage_digest(_report(files), _SELECTION, max_modules=0)

        assert len(digest.splitlines()) <= 40
        assert "250 modules measured" in digest
        assert "… and" in digest
        assert "further modules have gaps" in digest

    def test_max_modules_zero_keeps_table_and_list(self) -> None:
        """max_modules=0 drops the gap ranking and nothing else."""
        files = {
            "src/pkg/a/m.py": _covered(),
            "src/pkg/b/x.py": _uncovered(3),
        }

        digest = format_coverage_digest(_report(files), _SELECTION, max_modules=0)

        assert "by package (statements, covered %):" in digest
        assert "    src/pkg/b/ (3 missing statements)" in digest
        assert "src/pkg/a/m.py" not in digest
        assert "1 further modules have gaps" in digest
