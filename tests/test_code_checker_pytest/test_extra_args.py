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

    def test_lone_s_flag_passes_through(self) -> None:
        """-s flag passes through when xdist is not active."""
        result = sanitize_extra_args(["-s", "-x"], None)
        assert result.cleaned_args == ["-s", "-x"]
        assert result.verbosity == 2
        assert result.notes == []

    def test_s_stripped_when_xdist_active(self) -> None:
        """-s is stripped when -n VALUE (VALUE != "0") is also present."""
        result = sanitize_extra_args(["-s", "-n", "auto"], None)
        assert result.cleaned_args == ["-n", "auto"]
        assert result.verbosity == 2
        assert len(result.notes) == 1
        assert "xdist" in result.notes[0]

    def test_s_preserved_with_n_zero(self) -> None:
        """-s is preserved when -n 0 is used (xdist disabled)."""
        result = sanitize_extra_args(["-s", "-n", "0"], None)
        assert result.cleaned_args == ["-s", "-n", "0"]
        assert result.verbosity == 2
        assert result.notes == []

    def test_numprocesses_long_form_does_not_trigger_strip(self) -> None:
        """--numprocesses long form does not trigger -s strip (documented limitation)."""
        result = sanitize_extra_args(["-s", "--numprocesses", "auto"], None)
        assert result.cleaned_args == ["-s", "--numprocesses", "auto"]
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
        assert result.cleaned_args == ["-s", "-x"]
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

    def test_xdist_worker_count_no_false_positive(self) -> None:
        """`-n auto` does not produce a 'not found' note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_extra_args(["-n", "auto"], None, project_dir=tmpdir)
            assert result.has_path_args is False
            assert result.cleaned_args == ["-n", "auto"]
            assert not any("not found" in n for n in result.notes)

    def test_marker_expression_without_markers_param_no_false_positive(self) -> None:
        """`-m "not integration"` (no markers param) does not produce a 'not found' note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_extra_args(
                ["-m", "not integration"], None, project_dir=tmpdir
            )
            assert result.has_path_args is False
            assert result.cleaned_args == ["-m", "not integration"]
            assert not any("not found" in n for n in result.notes)

    def test_keyword_expression_no_false_positive(self) -> None:
        """`-k "test_foo or test_bar"` does not produce a 'not found' note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_extra_args(
                ["-k", "test_foo or test_bar"], None, project_dir=tmpdir
            )
            assert result.has_path_args is False
            assert result.cleaned_args == ["-k", "test_foo or test_bar"]
            assert not any("not found" in n for n in result.notes)

    def test_maxfail_numeric_value_no_false_positive(self) -> None:
        """`--maxfail 3` does not produce a 'not found' note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_extra_args(["--maxfail", "3"], None, project_dir=tmpdir)
            assert result.has_path_args is False
            assert result.cleaned_args == ["--maxfail", "3"]
            assert not any("not found" in n for n in result.notes)

    def test_combined_xdist_and_marker_no_false_positives(self) -> None:
        """Combined `-n auto -m "not integration"` produces no 'not found' notes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sanitize_extra_args(
                ["-n", "auto", "-m", "not integration"], None, project_dir=tmpdir
            )
            assert result.has_path_args is False
            assert result.cleaned_args == ["-n", "auto", "-m", "not integration"]
            assert not any("not found" in n for n in result.notes)

    def test_flag_value_coexists_with_real_path(self) -> None:
        """Flag value `auto` is silent while a real file path is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = os.path.join(tmpdir, "tests")
            os.makedirs(tests_dir)
            test_file = os.path.join(tests_dir, "test_file.py")
            with open(test_file, "w") as f:
                f.write("")
            result = sanitize_extra_args(
                ["-n", "auto", "tests/test_file.py"], None, project_dir=tmpdir
            )
            assert result.has_path_args is True
            assert result.cleaned_args == ["-n", "auto", "tests/test_file.py"]
            assert not any("not found" in n for n in result.notes)
            assert not any("'auto'" in n for n in result.notes)
