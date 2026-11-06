"""Tests for narrowing and rendering the saved coverage run."""

from pathlib import Path
from typing import Any

import pytest

from mcp_tools_py.code_checker_pytest.coverage_store import (
    format_last_run,
    narrow_files,
    write_saved,
)
from tests.test_code_checker_pytest._coverage_report import (
    _file,
    _run,
    _saved,
    _write_metadata,
    _write_source,
)

_A = "src/pkg/a.py"
_B = "src/pkg/sub/b.py"
_C = "src/other/c.py"
_FILES: dict[str, Any] = {_A: {}, _B: {}, _C: {}}


class TestNarrowFiles:
    """Test narrowing a saved report to directories that were measured."""

    @pytest.mark.parametrize(
        ("paths", "kept"),
        [
            pytest.param(["src/pkg"], [_A, _B], id="sub-path"),
            pytest.param(["src/pkg/sub", "src/other"], [_B, _C], id="union"),
            pytest.param(["src"], [_A, _B, _C], id="equal-to-source"),
            pytest.param(["src\\pkg"], [_A, _B], id="backslash-path"),
            pytest.param(["./src/pkg/"], [_A, _B], id="unnormalized-path"),
        ],
    )
    def test_keeps_the_files_under_the_paths(
        self, paths: list[str], kept: list[str]
    ) -> None:
        """Only files below one of the paths stay."""
        assert list(narrow_files(_FILES, ["src"], paths)) == kept

    def test_windows_style_keys_match_and_stay_as_they_are(self) -> None:
        """Keys are compared normalized and returned unchanged."""
        files: dict[str, Any] = {
            "src\\pkg\\a.py": {"summary": {}},
            "src\\other\\c.py": {},
        }

        assert narrow_files(files, ["src"], ["src/pkg"]) == {
            "src\\pkg\\a.py": {"summary": {}}
        }

    def test_dot_is_allowed_when_it_is_the_measured_source(self) -> None:
        """A path equal to a measured source is allowed, also for the root."""
        assert narrow_files(_FILES, ["."], ["."]) == _FILES

    @pytest.mark.parametrize(
        ("measured", "paths", "named"),
        [
            pytest.param(["src"], ["src/pk"], "src/pk", id="whole-components"),
            pytest.param(["src"], ["."], ".", id="dot"),
            pytest.param(["src/pkg"], ["src"], "src", id="parent-of-source"),
            pytest.param(["src"], ["mypkg"], "mypkg", id="package-name"),
            pytest.param(["src"], ["/abs/src"], "/abs/src", id="absolute-posix"),
            pytest.param(["src"], ["C:\\abs\\src"], "C:\\abs\\src", id="absolute-win"),
            pytest.param(["src"], ["src/pkg", "nope"], "nope", id="one-of-two"),
        ],
    )
    def test_refuses(self, measured: list[str], paths: list[str], named: str) -> None:
        """The refusal names the path and asks for a directory."""
        result = narrow_files(_FILES, measured, paths)

        assert isinstance(result, str)
        assert f"'{named}'" in result
        assert f"directory under the measured sources: {measured[0]}" in result


class TestFormatLastRun:
    """Test the reply of a reuse call."""

    NO_RUN = "No saved coverage run. Run with coverage=True first."

    @staticmethod
    def _save(project: Path, **changes: Any) -> None:
        """Save a run whose freshness scope is empty, so it is always fresh."""
        branched = _file(10, [1, 2, 3, 4])
        branched["summary"].update(num_branches=4, covered_branches=1)
        files = {"src/pkg/a.py": branched, "src/other/c.py": _file(100, [])}
        saved = _saved(report={"files": files}, hashes={}, roots=[], **changes)
        write_saved(str(project), saved, None)

    def test_no_saved_run(self, tmp_path: Path) -> None:
        """The reply says what to do."""
        assert format_last_run(str(tmp_path), None, 10) == self.NO_RUN

    def test_corrupt_metadata_reads_as_no_saved_run(self, tmp_path: Path) -> None:
        """Corrupt metadata isn't an error."""
        _write_metadata(tmp_path, b"{not json")

        assert format_last_run(str(tmp_path), None, 10) == self.NO_RUN

    def test_without_narrowing_shows_everything(self, tmp_path: Path) -> None:
        """An empty coverage_source doesn't narrow."""
        self._save(tmp_path)

        result = format_last_run(str(tmp_path), [], 10)

        assert result.startswith("93.9%  110 stmts  4 missed  |  2 modules measured")

    def test_narrowed_header_counts_the_narrowed_files_with_branches(
        self, tmp_path: Path
    ) -> None:
        """(6 + 1) / (10 + 4) is 50%; lines alone would give 60%."""
        self._save(tmp_path)

        result = format_last_run(str(tmp_path), ["src/pkg"], 10)

        assert result.startswith("50.0%  10 stmts  4 missed  |  1 modules measured")
        assert "src/other" not in result

    def test_refused_narrowing_is_the_reply(self, tmp_path: Path) -> None:
        """A path outside what was measured gives no numbers."""
        self._save(tmp_path)

        result = format_last_run(str(tmp_path), ["lib"], 10)

        assert "'lib'" in result
        assert "stmts" not in result

    def test_repeats_the_saved_selection_warnings_and_fail_under(
        self, tmp_path: Path
    ) -> None:
        """The numbers still come from that run, so its qualifiers stay."""
        runs = [
            _run(selection="selection: a", failed_collectors=2),
            _run(selection="selection: b", failed_tests=1, generic_warning=True),
        ]
        self._save(tmp_path, runs=runs, fail_under=80.0)

        lines = format_last_run(str(tmp_path), None, 10).splitlines()

        assert lines[0].startswith("⚠ 2 collectors failed")
        assert lines[1].startswith("⚠ 1 test failed")
        assert lines[2].startswith("⚠ the pytest run reported an error")
        assert lines[4] == "selection: a + b"
        assert lines[5] == "fail_under=80 is configured; not applied to this run"

    def test_max_modules_limits_the_ranking(self, tmp_path: Path) -> None:
        """max_modules reaches the digest."""
        self._save(tmp_path)

        assert "src/pkg/a.py  4 missing" in format_last_run(str(tmp_path), None, 1)
        assert "src/pkg/a.py  4 missing" not in format_last_run(str(tmp_path), None, 0)

    def test_edited_new_and_deleted_files_count_as_changes(
        self, tmp_path: Path
    ) -> None:
        """Each changed file counts, and no numbers are returned."""
        _write_source(tmp_path, "src/edited.py", "x = 2\n")
        _write_source(tmp_path, "src/new.py")
        hashes = {"src/edited.py": "old", "src/deleted.py": "old"}
        write_saved(str(tmp_path), _saved(hashes=hashes, roots=["src"]), None)

        assert format_last_run(str(tmp_path), None, 10) == (
            "stale — rerun: 3 files changed since the last coverage run. "
            "Run with coverage=True."
        )

    def test_one_changed_file_reads_in_the_singular(self, tmp_path: Path) -> None:
        """The count and the noun agree."""
        _write_source(tmp_path, "src/new.py")
        write_saved(str(tmp_path), _saved(hashes={}, roots=["src"]), None)

        assert "stale — rerun: 1 file changed" in format_last_run(
            str(tmp_path), None, 10
        )
