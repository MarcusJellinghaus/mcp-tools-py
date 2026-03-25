"""Unit tests for sanitize_extra_args() function."""

import os
import tempfile

import pytest

from mcp_tools_py.code_checker_pytest.models import SanitizedArgs
from mcp_tools_py.code_checker_pytest.utils import sanitize_extra_args


class TestSanitizeExtraArgs:
    """Tests for the sanitize_extra_args function."""

    def test_no_extra_args_returns_defaults(self) -> None:
        """When no extra_args provided, return defaults."""
        result = sanitize_extra_args(None, None)
        assert result == SanitizedArgs(cleaned_args=[], verbosity=2, notes=[])

    def test_passthrough_unrelated_args(self) -> None:
        """Unrelated args pass through unchanged."""
        result = sanitize_extra_args(["-x", "--tb=short"], None)
        assert result.cleaned_args == ["-x", "--tb=short"]
        assert result.verbosity == 2
        assert result.notes == []

    @pytest.mark.parametrize(
        "flag,expected_verbosity",
        [
            ("-v", 1),
            ("-vv", 2),
            ("-vvv", 3),
        ],
    )
    def test_v_flag_extracts_verbosity(
        self, flag: str, expected_verbosity: int
    ) -> None:
        """Verbosity flags are extracted and removed from args."""
        result = sanitize_extra_args([flag], None)
        assert result.cleaned_args == []
        assert result.verbosity == expected_verbosity

    def test_v_flag_mixed_with_other_args(self) -> None:
        """Verbosity flag is extracted while other args pass through."""
        result = sanitize_extra_args(["-x", "-vvv", "--tb=short"], None)
        assert result.cleaned_args == ["-x", "--tb=short"]
        assert result.verbosity == 3

    def test_s_flag_removed_silently(self) -> None:
        """-s flag is removed silently (always auto-added)."""
        result = sanitize_extra_args(["-s", "-x"], None)
        assert result.cleaned_args == ["-x"]
        assert result.verbosity == 2
        assert result.notes == []

    def test_m_flag_removed_when_markers_provided(self) -> None:
        """-m flag and its value are removed when markers parameter is used."""
        result = sanitize_extra_args(["-m", "slow"], ["integration"])
        assert result.cleaned_args == []
        assert result.verbosity == 2
        assert len(result.notes) == 1
        assert "-m flag" in result.notes[0]
        assert "ignored" in result.notes[0]

    def test_m_flag_kept_when_no_markers(self) -> None:
        """-m flag and its value are kept when no markers parameter."""
        result = sanitize_extra_args(["-m", "slow"], None)
        assert result.cleaned_args == ["-m", "slow"]
        assert result.verbosity == 2
        assert result.notes == []

    def test_tests_path_removed(self) -> None:
        """Bare 'tests' or 'tests/' path is removed (auto-appended)."""
        result_tests = sanitize_extra_args(["tests"], None)
        assert result_tests.cleaned_args == []
        assert result_tests.verbosity == 2

        result_tests_slash = sanitize_extra_args(["tests/"], None)
        assert result_tests_slash.cleaned_args == []
        assert result_tests_slash.verbosity == 2

    def test_test_path_selector_preserved(self) -> None:
        """Specific test paths with :: selectors or filenames are preserved."""
        result_selector = sanitize_extra_args(
            ["tests/test_file.py::test_func", "-x"], None
        )
        assert result_selector.cleaned_args == ["tests/test_file.py::test_func", "-x"]
        assert result_selector.verbosity == 2
        assert result_selector.notes == []

        result_file = sanitize_extra_args(["tests/test_file.py", "-x"], None)
        assert result_file.cleaned_args == ["tests/test_file.py", "-x"]
        assert result_file.verbosity == 2
        assert result_file.notes == []

    def test_combined_deduplication(self) -> None:
        """All deduplication rules work together."""
        result = sanitize_extra_args(
            ["-s", "-vvv", "-m", "slow", "tests", "-x"], ["unit"]
        )
        assert result.cleaned_args == ["-x"]
        assert result.verbosity == 3
        assert len(result.notes) == 1
        assert "-m flag" in result.notes[0]


class TestSanitizeExtraArgsPathDetection:
    """Tests for path detection in sanitize_extra_args."""

    def test_existing_file_sets_has_path_args(self) -> None:
        """An existing file path sets has_path_args=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_example.py")
            with open(test_file, "w") as f:
                f.write("")
            result = sanitize_extra_args(["test_example.py"], None, project_dir=tmpdir)
            assert result.has_path_args is True
            assert any("Path argument" in n for n in result.notes)

    def test_existing_directory_sets_has_path_args(self) -> None:
        """An existing directory path sets has_path_args=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = os.path.join(tmpdir, "subdir")
            os.makedirs(sub)
            result = sanitize_extra_args(["subdir"], None, project_dir=tmpdir)
            assert result.has_path_args is True

    def test_node_id_with_existing_file_sets_has_path_args(self) -> None:
        """A node ID (file::test) with existing file sets has_path_args=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_example.py")
            with open(test_file, "w") as f:
                f.write("")
            result = sanitize_extra_args(
                ["test_example.py::test_func"], None, project_dir=tmpdir
            )
            assert result.has_path_args is True

    def test_nonexistent_path_keeps_has_path_args_false(self) -> None:
        """A non-existent path keeps has_path_args=False and adds a note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_extra_args(["no_such_file.py"], None, project_dir=tmpdir)
            assert result.has_path_args is False
            assert any("not found" in n for n in result.notes)

    def test_absolute_path_keeps_has_path_args_false(self) -> None:
        """An absolute path keeps has_path_args=False and adds a note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "test_example.py")
            with open(abs_path, "w") as f:
                f.write("")
            result = sanitize_extra_args([abs_path], None, project_dir=tmpdir)
            assert result.has_path_args is False
            assert any("absolute path" in n.lower() for n in result.notes)

    def test_mixed_args_detects_paths(self) -> None:
        """Flags are skipped, only real paths trigger has_path_args."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_example.py")
            with open(test_file, "w") as f:
                f.write("")
            result = sanitize_extra_args(
                ["-x", "test_example.py", "--tb=short"], None, project_dir=tmpdir
            )
            assert result.has_path_args is True
            assert "-x" in result.cleaned_args
            assert "--tb=short" in result.cleaned_args

    def test_empty_project_dir_keeps_has_path_args_false(self) -> None:
        """Default empty project_dir keeps has_path_args=False."""
        result = sanitize_extra_args(["test_example.py"], None)
        assert result.has_path_args is False

    def test_existing_tests_unchanged_with_defaults(self) -> None:
        """Backward compat: no project_dir means has_path_args defaults False."""
        result = sanitize_extra_args(["-x", "--tb=short"], None)
        assert result.has_path_args is False
        assert result.cleaned_args == ["-x", "--tb=short"]
