"""Tests for the saved coverage store."""

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from mcp_tools_py.code_checker_pytest.coverage_store import (
    METADATA_FILE,
    STORE_DIR,
    STORE_VERSION,
    clear_saved,
    freshness_roots,
    hash_python_files,
    load_saved,
    write_saved,
)


def _make_dirs(project: Path, *names: str) -> None:
    """Create directories below the project."""
    for name in names:
        (project / name).mkdir(parents=True)


def _write_layout(project: Path, where: str, testpaths: str) -> None:
    """Write a pyproject.toml naming the source and test directories."""
    (project / "pyproject.toml").write_text(
        f"[tool.setuptools.packages.find]\nwhere = {where}\n\n"
        f"[tool.pytest.ini_options]\ntestpaths = {testpaths}\n",
        encoding="utf-8",
    )


def _write_source(project: Path, relative: str, content: str = "x = 1\n") -> Path:
    """Write one file below the project, with its parent directories."""
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _run(**changes: Any) -> dict[str, Any]:
    """One run entry, as the callers build it."""
    return {
        "selection": "selection: full suite (no markers, -k or path arguments)",
        "data_file": None,
        "failed_collectors": 0,
        "failed_tests": 0,
        "generic_warning": False,
        **changes,
    }


def _saved(**changes: Any) -> dict[str, Any]:
    """The dict a caller passes to write_saved."""
    return {
        "report": {"files": {"src/a.py": {"summary": {"num_statements": 1}}}},
        "hashes": {"src/a.py": "abc"},
        "roots": ["src", "tests"],
        "sources": ["src"],
        "fail_under": 0.0,
        "runs": [_run()],
        **changes,
    }


def _metadata(**changes: Any) -> bytes:
    """The content of a valid metadata file, with some keys replaced."""
    return json.dumps({"version": STORE_VERSION, **_saved(), **changes}).encode()


def _metadata_without(key: str) -> bytes:
    """The content of a metadata file lacking one top-level key."""
    document = {"version": STORE_VERSION, **_saved()}
    del document[key]
    return json.dumps(document).encode()


def _run_without(key: str) -> dict[str, Any]:
    """A run entry lacking one key."""
    run = _run()
    del run[key]
    return run


def _write_metadata(project: Path, content: bytes) -> None:
    """Put raw content where load_saved reads the metadata."""
    store = project / STORE_DIR
    store.mkdir(parents=True)
    (store / METADATA_FILE).write_bytes(content)


class TestFreshnessRoots:
    """Test which directories decide whether saved data is still fresh."""

    def test_collects_all_kinds_of_directories(self, tmp_path: Path) -> None:
        """Source, explicit, test directories and test_folder are all roots."""
        _write_layout(tmp_path, '["src"]', '["tests", "integration"]')
        _make_dirs(tmp_path, "src", "lib", "tests", "integration", "extra")

        assert freshness_roots(str(tmp_path), ["lib"], "extra") == [
            "src",
            "lib",
            "tests",
            "integration",
            "extra",
        ]

    def test_package_name_in_coverage_source_is_skipped(self, tmp_path: Path) -> None:
        """A coverage_source entry that is no directory adds no root."""
        _write_layout(tmp_path, '["src"]', '["tests"]')
        _make_dirs(tmp_path, "src", "tests")

        assert freshness_roots(str(tmp_path), ["mypkg"], "tests") == ["src", "tests"]

    def test_flat_layout_does_not_include_the_project(self, tmp_path: Path) -> None:
        """where = ["."] gives no source root and doesn't raise."""
        _write_layout(tmp_path, '["."]', '["tests"]')
        _make_dirs(tmp_path, "lib", "tests")

        assert freshness_roots(str(tmp_path), ["lib"], "tests") == ["lib", "tests"]

    def test_invalid_pyproject_keeps_the_arguments(self, tmp_path: Path) -> None:
        """Invalid TOML costs the configured roots, without raising."""
        (tmp_path / "pyproject.toml").write_text("invalid {{{{", encoding="utf-8")
        _make_dirs(tmp_path, "src", "lib", "checks")

        assert freshness_roots(str(tmp_path), ["lib"], "checks") == ["lib", "checks"]

    def test_dedupes_by_normalized_path(self, tmp_path: Path) -> None:
        """Spellings of one directory give one normalized root."""
        _write_layout(tmp_path, '["src"]', '["tests"]')
        _make_dirs(tmp_path, "src", "tests")

        assert freshness_roots(str(tmp_path), ["./src", "src/"], "tests/") == [
            "src",
            "tests",
        ]

    def test_missing_directories_are_dropped(self, tmp_path: Path) -> None:
        """Nothing that isn't on disk is a root."""
        _write_layout(tmp_path, '["src"]', '["tests"]')

        assert not freshness_roots(str(tmp_path), None, "tests")


class TestHashPythonFiles:
    """Test the mapping of Python files to digests."""

    def test_keys_are_posix_relative_paths(self, tmp_path: Path) -> None:
        """Keys use forward slashes and values are SHA-256 of the bytes."""
        (tmp_path / "src" / "pkg").mkdir(parents=True)
        (tmp_path / "src" / "pkg" / "a.py").write_bytes(b"x = 1\n")

        assert hash_python_files(str(tmp_path), ["src"]) == {
            "src/pkg/a.py": hashlib.sha256(b"x = 1\n").hexdigest()
        }

    def test_prunes_environments_hidden_and_cache_directories(
        self, tmp_path: Path
    ) -> None:
        """Only regular source directories are walked."""
        _write_source(tmp_path, "src/keep.py")
        _write_source(tmp_path, "src/.venv/pyvenv.cfg", "home = x\n")
        _write_source(tmp_path, "src/.venv/skip.py")
        _write_source(tmp_path, "src/env/pyvenv.cfg", "home = x\n")
        _write_source(tmp_path, "src/env/skip.py")
        _write_source(tmp_path, "src/.hidden/skip.py")
        _write_source(tmp_path, "src/__pycache__/skip.py")

        assert list(hash_python_files(str(tmp_path), ["src"])) == ["src/keep.py"]

    def test_ignores_other_file_types(self, tmp_path: Path) -> None:
        """Only .py files are hashed."""
        _write_source(tmp_path, "src/a.py")
        _write_source(tmp_path, "src/data.txt")
        _write_source(tmp_path, "src/b.pyc")

        assert list(hash_python_files(str(tmp_path), ["src"])) == ["src/a.py"]

    def test_edit_add_and_delete_change_the_mapping(self, tmp_path: Path) -> None:
        """Each kind of change gives a different mapping."""
        source = _write_source(tmp_path, "src/a.py")
        original = hash_python_files(str(tmp_path), ["src"])
        assert hash_python_files(str(tmp_path), ["src"]) == original

        source.write_text("x = 2\n", encoding="utf-8")
        edited = hash_python_files(str(tmp_path), ["src"])
        assert edited != original

        added = _write_source(tmp_path, "src/b.py")
        assert hash_python_files(str(tmp_path), ["src"]) != edited

        added.unlink()
        assert hash_python_files(str(tmp_path), ["src"]) == edited
        source.unlink()
        assert not hash_python_files(str(tmp_path), ["src"])

    def test_unreadable_file_is_stored_as_such(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An OSError on one file doesn't raise."""
        _write_source(tmp_path, "src/a.py")

        def refuse(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("denied")

        monkeypatch.setattr(hashlib, "file_digest", refuse)

        assert hash_python_files(str(tmp_path), ["src"]) == {"src/a.py": "unreadable"}

    def test_root_on_another_drive_keeps_its_own_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file with no relative path to the project doesn't raise."""
        source = _write_source(tmp_path, "src/a.py")

        def no_relative_path(*_args: Any, **_kwargs: Any) -> str:
            raise ValueError("path is on mount 'D:'")

        monkeypatch.setattr(os.path, "relpath", no_relative_path)

        assert list(hash_python_files(str(tmp_path), ["src"])) == [source.as_posix()]


class TestWriteAndLoad:
    """Test saving and reading the metadata."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """What was written is what load_saved returns, with the version."""
        saved = _saved()

        write_saved(str(tmp_path), saved, None)

        loaded = load_saved(str(tmp_path))
        assert loaded == {**_saved(), "version": STORE_VERSION}
        assert loaded == saved

    def test_file_is_compact(self, tmp_path: Path) -> None:
        """A report read from a pretty-printed file is stored on one line."""
        pretty = json.dumps({"files": {"src/a.py": {"lines": [1, 2]}}}, indent=4)

        write_saved(str(tmp_path), _saved(report=json.loads(pretty)), None)

        content = (tmp_path / STORE_DIR / METADATA_FILE).read_bytes()
        assert b"\n" not in content
        assert b'": ' not in content

    def test_gitignore_is_written_and_recreated(self, tmp_path: Path) -> None:
        """The store ignores itself, also after the file was deleted."""
        gitignore = tmp_path / STORE_DIR / ".gitignore"

        write_saved(str(tmp_path), _saved(), None)
        assert gitignore.read_text(encoding="utf-8").strip() == "*"

        gitignore.unlink()
        write_saved(str(tmp_path), _saved(), None)
        assert gitignore.read_text(encoding="utf-8").strip() == "*"

    def test_missing_data_file_is_tolerated(self, tmp_path: Path) -> None:
        """A data file that doesn't exist leaves data_file None."""
        saved = _saved(runs=[_run(data_file="stale")])

        write_saved(str(tmp_path), saved, str(tmp_path / "nothing.coverage"))

        loaded = load_saved(str(tmp_path))
        assert loaded is not None
        assert loaded["runs"][-1]["data_file"] is None

    def test_data_file_is_copied_under_a_unique_name(self, tmp_path: Path) -> None:
        """The newest run references a copy, and each save gets a new name."""
        data_file = tmp_path / ".coverage"
        data_file.write_bytes(b"data")
        first = _saved()
        second = _saved()

        write_saved(str(tmp_path), first, str(data_file))
        write_saved(str(tmp_path), second, str(data_file))

        first_name = first["runs"][-1]["data_file"]
        second_name = second["runs"][-1]["data_file"]
        assert re.fullmatch(r"run-[0-9a-f-]{36}\.coverage", second_name)
        assert first_name != second_name
        assert (tmp_path / STORE_DIR / second_name).read_bytes() == b"data"
        assert data_file.exists()

    def test_only_unreferenced_data_files_are_deleted(self, tmp_path: Path) -> None:
        """Cleanup after the replace keeps what the runs reference."""
        data_file = tmp_path / ".coverage"
        data_file.write_bytes(b"data")
        store = tmp_path / STORE_DIR
        store.mkdir(parents=True)
        (store / "run-kept.coverage").write_bytes(b"kept")
        (store / "run-orphan.coverage").write_bytes(b"orphan")
        saved = _saved(runs=[_run(data_file="run-kept.coverage"), _run()])

        write_saved(str(tmp_path), saved, str(data_file))

        assert sorted(path.name for path in store.glob("run-*.coverage")) == sorted(
            ["run-kept.coverage", saved["runs"][-1]["data_file"]]
        )

    def test_failed_replace_removes_the_temp_file_and_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The previous metadata survives, and no temp file stays behind."""
        write_saved(str(tmp_path), _saved(fail_under=1.0), None)
        store = tmp_path / STORE_DIR
        before = sorted(path.name for path in store.iterdir())

        def refuse(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("locked")

        monkeypatch.setattr(os, "replace", refuse)

        with pytest.raises(OSError, match="locked"):
            write_saved(str(tmp_path), _saved(fail_under=2.0), None)

        assert sorted(path.name for path in store.iterdir()) == before
        loaded = load_saved(str(tmp_path))
        assert loaded is not None
        assert loaded["fail_under"] == 1.0

    def test_no_file_loads_as_none(self, tmp_path: Path) -> None:
        """A project that never saved has no saved data."""
        assert load_saved(str(tmp_path)) is None

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(b"{not json", id="corrupt-json"),
            pytest.param(b"\xff\xfe\x00", id="not-utf8"),
            pytest.param(b"[1, 2]", id="json-list"),
            pytest.param(_metadata(version=STORE_VERSION + 1), id="wrong-version"),
            pytest.param(_metadata_without("version"), id="no-version"),
            pytest.param(_metadata_without("report"), id="no-report"),
            pytest.param(_metadata_without("hashes"), id="no-hashes"),
            pytest.param(_metadata_without("roots"), id="no-roots"),
            pytest.param(_metadata_without("sources"), id="no-sources"),
            pytest.param(_metadata_without("fail_under"), id="no-fail-under"),
            pytest.param(_metadata_without("runs"), id="no-runs"),
            pytest.param(_metadata(report=[]), id="report-not-dict"),
            pytest.param(_metadata(report={}), id="report-no-files"),
            pytest.param(_metadata(report={"files": []}), id="files-not-dict"),
            pytest.param(_metadata(hashes=[]), id="hashes-not-dict"),
            pytest.param(_metadata(roots={}), id="roots-not-list"),
            pytest.param(_metadata(sources="src"), id="sources-not-list"),
            pytest.param(_metadata(runs={}), id="runs-not-list"),
            pytest.param(_metadata(runs=["run"]), id="run-not-dict"),
            *(
                pytest.param(_metadata(runs=[_run_without(key)]), id=f"run-no-{key}")
                for key in _run()
            ),
        ],
    )
    def test_invalid_metadata_loads_as_none(
        self, tmp_path: Path, content: bytes
    ) -> None:
        """Anything but the expected structure counts as no saved data."""
        _write_metadata(tmp_path, content)

        assert load_saved(str(tmp_path)) is None


class TestClearSaved:
    """Test removing the saved data."""

    def test_removes_the_data(self, tmp_path: Path) -> None:
        """The whole store directory goes."""
        data_file = tmp_path / ".coverage"
        data_file.write_bytes(b"data")
        write_saved(str(tmp_path), _saved(), str(data_file))

        clear_saved(str(tmp_path))

        assert load_saved(str(tmp_path)) is None
        assert not (tmp_path / STORE_DIR).exists()

    def test_creates_nothing_without_a_store(self, tmp_path: Path) -> None:
        """A project with no store stays as it was."""
        clear_saved(str(tmp_path))

        assert not os.listdir(tmp_path)

    def test_oserror_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The caller decides what a failed clear means."""
        write_saved(str(tmp_path), _saved(), None)

        def refuse(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("locked")

        monkeypatch.setattr(shutil, "rmtree", refuse)

        with pytest.raises(OSError, match="locked"):
            clear_saved(str(tmp_path))
