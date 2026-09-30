"""Tests for the shared report-count helpers."""

import pytest

from mcp_tools_py.utils.report_counts import (
    format_dir_split,
    format_total_line,
    plural,
)


@pytest.mark.parametrize(
    ("count", "word", "expected"),
    [
        (1, "issue", "1 issue"),
        (3, "occurrence", "3 occurrences"),
        (0, "rule", "0 rules"),
    ],
)
def test_plural(count: int, word: str, expected: str) -> None:
    assert plural(count, word) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/a.py", "(src: 1)"),
        ("tests\\b.py", "(tests: 1)"),
        ("./src/a.py", "(src: 1)"),
        ("setup.py", "((root): 1)"),
        ("src/pkg/tests/a.py", "(src: 1)"),
        ("C:\\x\\a.py", "((outside): 1)"),
        ("c:/x/a.py", "((outside): 1)"),
        ("/abs/a.py", "((outside): 1)"),
        ("../a.py", "((outside): 1)"),
        ("..\\a.py", "((outside): 1)"),
        ("..", "((outside): 1)"),
        ("Command line", "((outside): 1)"),
    ],
)
def test_format_dir_split_single_path(path: str, expected: str) -> None:
    assert format_dir_split([path]) == expected


def test_format_dir_split_orders_by_count_then_name() -> None:
    paths = ["src/a.py", "tests\\b.py", "tests/c.py", "setup.py"]
    assert format_dir_split(paths) == "(tests: 2, (root): 1, src: 1)"


def test_format_dir_split_accepts_generator() -> None:
    assert format_dir_split(p for p in ["src/a.py", "src/b.py"]) == "(src: 2)"


@pytest.mark.parametrize(
    ("tool", "issues", "rules", "expected"),
    [
        ("ruff", 143, 8, "ruff found 143 issues across 8 rules"),
        ("mypy", 1, 1, "mypy found 1 issue across 1 rule"),
        ("bandit", 0, 0, "bandit found 0 issues across 0 rules"),
    ],
)
def test_format_total_line(tool: str, issues: int, rules: int, expected: str) -> None:
    assert format_total_line(tool, issues, rules) == expected
