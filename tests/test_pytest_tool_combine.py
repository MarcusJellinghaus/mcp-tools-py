"""Tests for run_pytest_check(combine_with_previous=True)."""

import importlib.util
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from mcp_coder_utils.toolkit import ActionRequest

from mcp_tools_py.code_checker_pytest.coverage_store import (
    METADATA_FILE,
    STORE_DIR,
    load_saved,
)
from mcp_tools_py.toolkit import PythonToolkit
from tests._coverage_project import _run_pytest_check, _write_project

FIRST = ["tests/test_mod.py"]
SECOND = ["tests/test_other.py"]
MERGE_FAILED = "Saved runs discarded: merging failed"

_OTHER_TEST = """\
from pkg.mod import uncovered


def test_uncovered():
    assert uncovered(1) == 2
"""


@pytest.fixture
def mock_pytest_run() -> Iterator[MagicMock]:
    """Stand in for the pytest run, which a refused call must never start."""
    with patch(
        "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
    ) as mock_run:
        yield mock_run


class TestArguments:
    """Test which arguments combining accepts, without a real project."""

    def test_requires_coverage(
        self, tmp_path: Path, mock_pytest_run: MagicMock
    ) -> None:
        """Without coverage there is nothing to merge, and pytest doesn't run."""
        result = _run_pytest_check(tmp_path)(combine_with_previous=True)

        assert result == "Error: combine_with_previous=True requires coverage=True."
        mock_pytest_run.assert_not_called()

    def test_refused_with_reuse(
        self, tmp_path: Path, mock_pytest_run: MagicMock
    ) -> None:
        """Reuse runs no tests, so it has nothing to combine."""
        result = _run_pytest_check(tmp_path)(
            use_last_coverage_run=True, combine_with_previous=True
        )

        assert result == (
            "Error: use_last_coverage_run=True cannot be used with: "
            "combine_with_previous."
        )
        mock_pytest_run.assert_not_called()


def _percent(result: str) -> float:
    """Read the total percentage from a digest.

    Returns:
        The number in the digest's header line.
    """
    match = re.search(r"([\d.]+)%\s+\d+ stmts", result)
    assert match is not None, result
    return float(match.group(1))


def _combine(project: Path, extra_args: list[str], **kwargs: Any) -> str:
    """Run one selection with coverage, merging it with the saved set.

    Returns:
        The tool's reply.
    """
    result: str = _run_pytest_check(project)(
        extra_args=extra_args, coverage=True, combine_with_previous=True, **kwargs
    )
    return result


def _saved_runs(project: Path) -> list[dict[str, Any]]:
    """Read the saved run entries.

    Returns:
        The ``runs`` entries of the metadata.
    """
    saved = load_saved(str(project))
    assert saved is not None
    runs: list[dict[str, Any]] = saved["runs"]
    return runs


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project where each of two test files covers one function."""
    _write_project(tmp_path)
    (tmp_path / "tests" / "test_other.py").write_text(_OTHER_TEST)
    return tmp_path


@pytest.mark.integration
@pytest.mark.skipif(
    importlib.util.find_spec("pytest_cov") is None,
    reason="pytest-cov is not installed",
)
class TestRealProject:
    """Test merging real coverage runs."""

    def test_two_selections_merge(self, project: Path) -> None:
        """The merged percentage beats either run and both selections are listed."""
        first = _combine(project, FIRST)
        second = _combine(project, SECOND)

        assert MERGE_FAILED not in second
        assert "Saved runs discarded" not in first
        assert _percent(second) > _percent(first)
        assert _percent(second) == 100.0
        assert (
            "selection: paths tests/test_mod.py + paths tests/test_other.py" in second
        )
        assert len(_saved_runs(project)) == 2

    def test_merge_beats_each_selection_alone(self, project: Path) -> None:
        """The second selection alone reaches less than the merge."""
        alone = _run_pytest_check(project)(extra_args=SECOND, coverage=True)
        _combine(project, FIRST)
        merged = _combine(project, SECOND)

        assert _percent(alone) < _percent(merged)

    def test_edited_source_discards_the_saved_runs(self, project: Path) -> None:
        """Data from another version of a file must not merge."""
        _combine(project, FIRST)
        with (project / "src" / "pkg" / "mod.py").open("a", encoding="utf-8") as file:
            file.write("# changed\n")

        result = _combine(project, SECOND)

        assert "Saved runs discarded: files changed since the saved runs." in result
        assert "selection: paths tests/test_other.py" in result
        assert "tests/test_mod.py +" not in result
        assert len(_saved_runs(project)) == 1

    def test_other_coverage_source_discards_the_saved_runs(self, project: Path) -> None:
        """Runs that measured different directories must not merge."""
        _combine(project, FIRST)

        result = _combine(project, SECOND, coverage_source=["src/pkg"])

        assert "Saved runs discarded: coverage_source changed." in result
        assert len(_saved_runs(project)) == 1

    def test_reuse_returns_the_merged_set(self, project: Path) -> None:
        """Reuse shows the merged numbers, selections and summed warnings."""
        tests = project / "tests"
        (tests / "test_fail_a.py").write_text("def test_a():\n    assert False\n")
        (tests / "test_fail_b.py").write_text("def test_b():\n    assert False\n")
        _combine(project, [*FIRST, "tests/test_fail_a.py"])
        merged = _combine(project, [*SECOND, "tests/test_fail_b.py"])
        assert MERGE_FAILED not in merged

        result = _run_pytest_check(project)(use_last_coverage_run=True)

        assert "⚠ 2 tests failed" in result
        assert _percent(result) == _percent(merged)
        assert (
            "selection: paths tests/test_mod.py, tests/test_fail_a.py"
            " + paths tests/test_other.py, tests/test_fail_b.py"
        ) in result

    def test_fail_under_does_not_fail_the_merge(self, project: Path) -> None:
        """A merged total below the configured 99 still gives a merged report."""
        (project / "src" / "pkg" / "never.py").write_text(
            "def never():\n    return 1\n"
        )
        _combine(project, FIRST)

        result = _combine(project, SECOND)

        assert MERGE_FAILED not in result
        assert 0 < _percent(result) < 99
        assert len(_saved_runs(project)) == 2

    def test_no_report_leaves_the_set_unchanged(self, project: Path) -> None:
        """A selection matching nothing costs nothing, and the reply says so."""
        _combine(project, FIRST)
        metadata = project / STORE_DIR / METADATA_FILE
        before = metadata.read_bytes()

        result = _combine(project, ["-k", "nomatch"])

        assert "Coverage report was not produced." in result
        assert "Saved coverage data was not changed." in result
        assert metadata.read_bytes() == before

    def test_rerun_replaces_its_selection(self, project: Path) -> None:
        """Rerunning one of two selections keeps two entries and data files."""
        _combine(project, FIRST)
        _combine(project, SECOND)

        result = _combine(project, FIRST)

        assert MERGE_FAILED not in result
        assert _percent(result) == 100.0
        assert len(_saved_runs(project)) == 2
        assert len(list((project / STORE_DIR).glob("run-*.coverage"))) == 2

    def test_toolkit_full_depth_replaces_the_set(self, project: Path) -> None:
        """Full depth never merges, and what it saved can be merged with later."""
        _combine(project, FIRST)
        _combine(project, SECOND)

        PythonToolkit().run(
            ActionRequest(action="test", depth="full", project_dir=project, params={})
        )

        assert len(_saved_runs(project)) == 1

        result = _combine(project, FIRST)

        assert MERGE_FAILED not in result
        assert len(_saved_runs(project)) == 2
