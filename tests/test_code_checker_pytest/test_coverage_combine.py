"""Tests for merging a finished coverage run with the saved runs."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.code_checker_pytest.coverage_store import (
    METADATA_FILE,
    STORE_DIR,
    CoverageRun,
    _mismatch_reason,
    finish_coverage_run,
    load_saved,
    start_coverage_run,
)
from mcp_tools_py.code_checker_pytest.models import Collector, PytestReport, Summary
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from tests.test_code_checker_pytest._coverage_report import (
    _coverage_run,
    _metadata,
    _run,
    _verdict,
    _write_metadata,
    _write_source,
)

_MERGED: dict[str, Any] = {"files": {"src/merged.py": {}}}
_NEW: dict[str, Any] = {"files": {"src/new.py": {}}}
_FAILED_MERGE = "Saved runs discarded: merging failed."


def _seed_runs(project: Path, run: CoverageRun, *entries: dict[str, Any]) -> None:
    """Save a set the run can merge with, with a data file per named entry."""
    _write_metadata(
        project,
        _metadata(hashes=run.hashes, sources=run.sources, runs=list(entries)),
    )
    for entry in entries:
        if entry["data_file"] is not None:
            (project / STORE_DIR / entry["data_file"]).write_bytes(b"old")


def _named(identity: str, **changes: Any) -> dict[str, Any]:
    """A saved run entry with a data file named after its identity."""
    return _run(identity=identity, data_file=f"run-{identity}.coverage", **changes)


@pytest.fixture
def mock_merge() -> Any:
    """Stand in for the coverage commands; the merge succeeds."""
    with patch(
        "mcp_tools_py.code_checker_pytest.coverage_store.merge_coverage_data",
        return_value=_MERGED,
    ) as mock:
        yield mock


class TestMismatchReason:
    """Test the conditions that keep saved runs from being merged."""

    @pytest.mark.parametrize(
        ("changes", "edit", "expected"),
        [
            pytest.param({}, False, None, id="same"),
            pytest.param(
                {"sources": ["lib"]}, False, "coverage_source changed", id="sources"
            ),
            pytest.param(
                {"hashes": {"src/a.py": "other"}},
                False,
                "files changed since the saved runs",
                id="saved-hashes",
            ),
            pytest.param({}, True, "files changed during this run", id="edit-now"),
        ],
    )
    def test_reason(
        self, tmp_path: Path, changes: dict[str, Any], edit: bool, expected: str | None
    ) -> None:
        """Sources are checked first, then saved hashes, then the current ones."""
        run = _coverage_run(tmp_path, tmp_path)
        saved = {"hashes": run.hashes, "sources": run.sources, **changes}
        if edit:
            _write_source(tmp_path, "src/a.py", "x = 2\n")

        assert _mismatch_reason(saved, run) == expected

    def test_none_and_equivalent_list_are_the_same_source(self, tmp_path: Path) -> None:
        """Sources compare resolved, normalized and sorted."""
        _write_source(tmp_path, "src/a.py")

        def start(raw: list[str] | None, sources: list[str]) -> CoverageRun:
            return start_coverage_run(
                str(tmp_path),
                "temp",
                "tests",
                raw,
                sources,
                None,
                "selection: x",
                "identity",
                "python",
                None,
                30,
            )

        first = start(None, ["src"])
        second = start(["./src"], ["./src"])

        saved = {"hashes": first.hashes, "sources": first.sources}
        assert _mismatch_reason(saved, second) is None


class TestCombine:
    """Test how a run with combine=True treats the saved set."""

    def test_merges_with_a_different_selection(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """The merged report and every selection and count come back."""
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / ".coverage").write_bytes(b"new")
        project = tmp_path / "project"
        run = _coverage_run(project, temp_dir, combine=True)
        _seed_runs(project, run, _named("old", selection="selection: old"))

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        store = project / STORE_DIR
        mock_merge.assert_called_once_with(
            "python",
            str(project),
            [str(store / "run-old.coverage"), str(temp_dir / ".coverage")],
            str(temp_dir),
            {"A": "1"},
            30,
        )
        assert finished.data == _MERGED
        assert finished.selection == "selection: old + markers 'x'"
        assert not finished.notes
        saved = load_saved(str(project))
        assert saved is not None
        assert saved["report"] == _MERGED
        assert [entry["identity"] for entry in saved["runs"]] == [
            "old",
            "identity-new",
        ]
        assert (store / "run-old.coverage").exists()
        assert (store / saved["runs"][-1]["data_file"]).read_bytes() == b"new"

    def test_locked_unreferenced_file_keeps_the_merged_digest(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """A failed cleanup after the replace doesn't read as a failed save."""
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / ".coverage").write_bytes(b"new")
        project = tmp_path / "project"
        run = _coverage_run(project, temp_dir, combine=True)
        _seed_runs(project, run, _named("old"))
        orphan = project / STORE_DIR / "run-orphan.coverage"
        orphan.write_bytes(b"orphan")

        with patch("pathlib.Path.unlink", side_effect=OSError("locked")) as unlink:
            finished = finish_coverage_run(run, _NEW, None, _verdict())

        unlink.assert_called_once()
        mock_merge.assert_called_once()
        assert finished.data == _MERGED
        assert not finished.notes
        saved = load_saved(str(project))
        assert saved is not None
        assert saved["report"] == _MERGED
        assert orphan.exists()

    def test_failed_merge_saves_only_the_new_run(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """The note is added and the old data files are deleted."""
        run = _coverage_run(tmp_path, tmp_path, combine=True)
        _seed_runs(tmp_path, run, _named("old"))
        mock_merge.return_value = None

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        assert finished.notes == [_FAILED_MERGE]
        assert finished.data == _NEW
        saved = load_saved(str(tmp_path))
        assert saved is not None
        assert saved["report"] == _NEW
        assert [entry["identity"] for entry in saved["runs"]] == ["identity-new"]
        assert not (tmp_path / STORE_DIR / "run-old.coverage").exists()

    def test_saved_run_without_a_data_file_counts_as_failed_merge(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """No merge is attempted, and nothing raises."""
        run = _coverage_run(tmp_path, tmp_path, combine=True)
        _seed_runs(tmp_path, run, _named("old"), _run(identity="no-data"))

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        mock_merge.assert_not_called()
        assert finished.notes == [_FAILED_MERGE]
        saved = load_saved(str(tmp_path))
        assert saved is not None
        assert [entry["identity"] for entry in saved["runs"]] == ["identity-new"]

    def test_mismatch_saves_only_the_new_run(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """A mismatch uses the same note format as a failed merge."""
        run = _coverage_run(tmp_path, tmp_path, combine=True)
        _seed_runs(tmp_path, run, _named("old"))
        _write_source(tmp_path, "src/a.py", "x = 2\n")

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        mock_merge.assert_not_called()
        assert finished.notes == [
            "Saved runs discarded: files changed during this run."
        ]
        saved = load_saved(str(tmp_path))
        assert saved is not None
        assert len(saved["runs"]) == 1

    @pytest.mark.parametrize(
        ("combine", "store_stays"),
        [
            pytest.param(True, True, id="combine"),
            pytest.param(False, False, id="plain"),
        ],
    )
    def test_no_report(self, tmp_path: Path, combine: bool, store_stays: bool) -> None:
        """Only a combining run leaves the set byte-identical, and says so."""
        run = _coverage_run(tmp_path, tmp_path, combine=combine)
        _seed_runs(tmp_path, run, _named("old"))
        metadata = tmp_path / STORE_DIR / METADATA_FILE
        before = metadata.read_bytes()

        finished = finish_coverage_run(run, None, None, _verdict(RunStatus.ERROR))

        assert finished.data is None
        if store_stays:
            assert metadata.read_bytes() == before
            assert finished.notes == ["Saved coverage data was not changed."]
        else:
            assert not (tmp_path / STORE_DIR).exists()
            assert not finished.notes

    def test_rerun_of_the_only_selection_replaces_it_without_merging(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """With nothing else saved there is nothing to merge."""
        run = _coverage_run(tmp_path, tmp_path, combine=True)
        _seed_runs(tmp_path, run, _named("identity-new"))

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        mock_merge.assert_not_called()
        assert finished.data == _NEW
        assert not finished.notes
        saved = load_saved(str(tmp_path))
        assert saved is not None
        assert len(saved["runs"]) == 1
        assert not (tmp_path / STORE_DIR / "run-identity-new.coverage").exists()

    def test_rerun_among_others_merges_only_the_others(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """The replaced selection's data and counts drop out."""
        run = _coverage_run(tmp_path, tmp_path, combine=True)
        _seed_runs(
            tmp_path,
            run,
            _named("identity-new", failed_tests=5),
            _named("old", failed_tests=2),
        )

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        assert mock_merge.call_args.args[2][0].endswith("run-old.coverage")
        assert len(mock_merge.call_args.args[2]) == 2
        assert finished.outcome["failed_tests"] == 2
        saved = load_saved(str(tmp_path))
        assert saved is not None
        assert [entry["identity"] for entry in saved["runs"]] == [
            "old",
            "identity-new",
        ]
        assert not (tmp_path / STORE_DIR / "run-identity-new.coverage").exists()

    @pytest.mark.usefixtures("mock_merge")
    def test_same_collector_count_in_two_selections_adds_up(
        self, tmp_path: Path
    ) -> None:
        """The sum is per merged run, with no check for the same collector."""
        report = PytestReport(
            created=0.0,
            duration=0.0,
            exitcode=1,
            root="",
            environment={},
            summary=Summary(collected=1, total=1, failed=1),
            collectors=[Collector(nodeid="tests/a", outcome="failed", result=[])],
        )
        run = _coverage_run(tmp_path, tmp_path, combine=True)
        _seed_runs(tmp_path, run, _named("old", failed_collectors=1, failed_tests=1))

        finished = finish_coverage_run(run, _NEW, report, _verdict(RunStatus.FAILED))

        assert finished.outcome == {
            "failed_collectors": 2,
            "failed_tests": 2,
            "generic_warning": False,
        }

    def test_first_combine_behaves_like_a_plain_run(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """No saved set means no merge and no note."""
        run = _coverage_run(tmp_path, tmp_path, combine=True)

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        mock_merge.assert_not_called()
        assert not finished.notes
        assert finished.data == _NEW

    def test_plain_run_replaces_the_set(
        self, tmp_path: Path, mock_merge: MagicMock
    ) -> None:
        """Merging is opt-in, and replacing a set adds no note."""
        run = _coverage_run(tmp_path, tmp_path)
        _seed_runs(tmp_path, run, _named("old"))

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        mock_merge.assert_not_called()
        assert not finished.notes
        saved = load_saved(str(tmp_path))
        assert saved is not None
        assert [entry["identity"] for entry in saved["runs"]] == ["identity-new"]

    def test_failed_save_gives_only_its_own_note(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing was discarded when the set couldn't be replaced."""
        run = _coverage_run(tmp_path, tmp_path, combine=True)
        _seed_runs(tmp_path, run, _named("old"))
        _write_source(tmp_path, "src/a.py", "x = 2\n")

        def refuse(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("locked")

        monkeypatch.setattr(os, "replace", refuse)

        finished = finish_coverage_run(run, _NEW, None, _verdict())

        assert finished.notes == ["Could not update saved coverage data: locked"]
