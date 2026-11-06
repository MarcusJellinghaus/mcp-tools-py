"""Tests for the digest's package table and the totals computed from files."""

from typing import Any

import pytest

from mcp_tools_py.code_checker_pytest.coverage import (
    _common_prefix,
    _package_table,
    format_coverage_digest,
    norm_path,
    percent_covered,
)
from tests.test_code_checker_pytest._coverage_report import _SELECTION, _file, _report

_TABLE_HEADER = "by package (statements, covered %):"


def _row_names(files: dict[str, Any]) -> list[str]:
    """The names in the package table, in table order."""
    return [line.split()[0] for line in _package_table(files)[1:]]


class TestPackageTable:
    """Test the per-package table of the digest."""

    def test_src_layout_gets_one_row_per_subpackage(self) -> None:
        """Rows are the subpackages, sorted by missing statements."""
        files = {
            "src/pkg/a/m.py": _file(10, [1, 2]),
            "src/pkg/a/deep/k.py": _file(10, [1]),
            "src/pkg/b/n.py": _file(100, list(range(1, 51))),
        }

        assert _package_table(files) == [
            _TABLE_HEADER,
            "    b     100  50%",
            "    a      20  85%",
        ]

    def test_ties_sort_by_name(self) -> None:
        """Rows with equal missing statements are in name order."""
        files = {"src/b/m.py": _file(10, [1]), "src/a/m.py": _file(10, [1])}

        assert _row_names(files) == ["a", "b"]

    def test_names_are_padded_to_the_longest(self) -> None:
        """The numbers line up whatever the name length."""
        files = {
            "src/workflows/m.py": _file(3105, [1]),
            "src/cli/m.py": _file(6200, list(range(1, 6201))),
        }

        assert _package_table(files)[1:] == [
            "    cli          6200   0%",
            "    workflows    3105 100%",
        ]

    def test_src_init_does_not_collapse_the_table(self) -> None:
        """A src/__init__.py with statements lands in (root), not in the prefix."""
        files = {
            "src/__init__.py": _file(4, [1]),
            "src/pkg/a/m.py": _file(10, [1, 2]),
            "src/pkg/b/n.py": _file(10, [1, 2, 3]),
        }

        assert _common_prefix(files) == ("src", "pkg")
        assert _row_names(files) == ["b", "a", "(root)"]
        assert _package_table(files)[3].split() == ["(root)", "4", "75%"]

    def test_files_directly_in_the_package_get_a_root_row(self) -> None:
        """Files with no directory below the prefix go in (root)."""
        files = {
            "src/pkg/top.py": _file(10, [1, 2]),
            "src/pkg/a/m.py": _file(10, [1]),
        }

        assert _row_names(files) == ["(root)", "a"]

    def test_files_outside_the_prefix_go_in_root(self) -> None:
        """An __init__.py outside the prefix keeps its statements in (root)."""
        files = {
            "other/__init__.py": _file(2, [1]),
            "src/pkg/a/m.py": _file(10, [1]),
            "src/pkg/b/n.py": _file(10, [1]),
        }

        assert _row_names(files) == ["(root)", "a", "b"]

    def test_windows_keys_group_like_posix_keys(self) -> None:
        """Backslash keys give the same table as forward-slash keys."""
        windows = {
            "src\\pkg\\a\\m.py": _file(10, [1, 2]),
            "src\\pkg\\b\\n.py": _file(10, [1]),
        }
        posix = {key.replace("\\", "/"): entry for key, entry in windows.items()}

        assert _package_table(windows) == _package_table(posix)
        assert _row_names(windows) == ["a", "b"]

    def test_prefix_matches_whole_components(self) -> None:
        """pkg_a and pkg_b share the prefix src, not src/pkg_."""
        files = {"src/pkg_a/m.py": _file(10, [1, 2]), "src/pkg_b/n.py": _file(10, [1])}

        assert _common_prefix(files) == ("src",)
        assert _row_names(files) == ["pkg_a", "pkg_b"]

    def test_only_init_files_give_an_empty_prefix(self) -> None:
        """With nothing but __init__.py files there is no prefix to strip."""
        files = {"src/__init__.py": _file(4, [1]), "src/a/__init__.py": _file(4, [1])}

        assert not _common_prefix(files)

    def test_empty_init_adds_no_root_row(self) -> None:
        """A 0-statement __init__.py doesn't add a (root) row."""
        files = {
            "src/pkg/__init__.py": _file(0, []),
            "src/pkg/a/m.py": _file(10, [1]),
            "src/pkg/b/n.py": _file(10, [1]),
        }

        assert _row_names(files) == ["a", "b"]

    def test_no_statements_gives_no_table(self) -> None:
        """Without a row to show, the header is left out too."""
        assert not _package_table({})
        assert not _package_table({"src/pkg/__init__.py": _file(0, [])})


class TestNormPath:
    """Test the path form used for comparing and grouping."""

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("src\\pkg\\m.py", "src/pkg/m.py"),
            ("src/pkg/m.py", "src/pkg/m.py"),
            ("./src//pkg/", "src/pkg"),
        ],
    )
    def test_norm_path(self, path: str, expected: str) -> None:
        """Backslashes become forward slashes and the path is normalized."""
        assert norm_path(path) == expected


class TestPercentCovered:
    """Test the percentage computed from file summaries."""

    @pytest.mark.parametrize(
        ("summaries", "expected"),
        [
            ([{"covered_lines": 1, "num_statements": 4}], 25.0),
            (
                [
                    {
                        "covered_lines": 4,
                        "covered_branches": 1,
                        "num_statements": 9,
                        "num_branches": 2,
                    }
                ],
                45.45,
            ),
            (
                [
                    {"covered_lines": 1, "num_statements": 2},
                    {"covered_lines": 2, "num_statements": 2},
                ],
                75.0,
            ),
            ([{}], 100.0),
            ([], 100.0),
        ],
        ids=["lines-only", "with-branches", "summed", "missing-keys", "no-summaries"],
    )
    def test_percent_covered(
        self, summaries: list[dict[str, Any]], expected: float
    ) -> None:
        """Lines and branches both count; a zero denominator gives 100.0."""
        assert percent_covered(summaries) == pytest.approx(expected, abs=0.01)

    def test_accepts_a_generator(self) -> None:
        """Any iterable of summaries works."""
        summaries = ({"covered_lines": 1, "num_statements": 2} for _ in range(2))

        assert percent_covered(summaries) == 50.0


class TestDigestFromFiles:
    """Test that the digest reads only the files of the report."""

    def test_header_needs_no_totals_key(self) -> None:
        """The header is summed from files when there are no totals."""
        data = {"files": {"a.py": _file(10, [3]), "b.py": _file(10, [1, 2, 3])}}

        lines = format_coverage_digest(data, _SELECTION).splitlines()

        assert lines[0] == "80.0%  20 stmts  4 missed  |  2 modules measured"

    def test_header_ignores_the_totals_key(self) -> None:
        """Totals that disagree with the files have no effect."""
        data = _report({"a.py": _file(10, [3])})
        data["totals"] = {"percent_covered": 1.0, "num_statements": 999}

        lines = format_coverage_digest(data, _SELECTION).splitlines()

        assert lines[0] == "90.0%  10 stmts  1 missed  |  1 modules measured"

    def test_table_sits_between_the_header_block_and_the_ranking(self) -> None:
        """The table follows selection and fail_under, after a blank line."""
        data = _report({"src/a/m.py": _file(10, [1], {"f": [1]})})

        lines = format_coverage_digest(data, _SELECTION, fail_under=80.0).splitlines()

        assert lines[1] == _SELECTION
        assert lines[2].startswith("fail_under=80")
        assert lines[3:6] == ["", _TABLE_HEADER, "    (root)      10  90%"]
        assert lines[6] == ""
        assert lines[7] == "src/a/m.py  1 missing  (90%)"

    def test_ranking_prints_report_keys_unchanged(self) -> None:
        """Normalizing is only for grouping; the ranking shows the raw key."""
        data = _report({"src\\a\\m.py": _file(10, [1], {"f": [1]})})

        assert "src\\a\\m.py  1 missing" in format_coverage_digest(data, _SELECTION)

    def test_no_files_gives_no_table(self) -> None:
        """An empty report has no table, and its header reads 100%."""
        digest = format_coverage_digest({"files": {}}, _SELECTION)

        assert "by package" not in digest
        assert digest.startswith("100.0%  0 stmts  0 missed  |  0 modules measured")
