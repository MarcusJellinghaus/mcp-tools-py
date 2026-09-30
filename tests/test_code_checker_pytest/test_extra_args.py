"""Unit tests for sanitize_extra_args() function."""

import os
import tempfile

import pytest

from mcp_tools_py.code_checker_pytest.models import SanitizedArgs
from mcp_tools_py.code_checker_pytest.utils import (
    SHOW_OUTPUT_NOTE,
    sanitize_extra_args,
)


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

    @pytest.mark.parametrize(
        "args,expected_cleaned,expected_verbosity",
        [
            (["-s"], [], 2),
            (["--capture=no"], [], 2),
            (["--capture", "no"], [], 2),
            (["-xvs"], ["-x"], 1),
            (["-qs"], ["-q"], 2),
            (["-vv", "-xvs"], ["-x"], 1),
            (["-s", "-n", "auto"], ["-n", "auto"], 2),
            (["-s", "-n", "0"], ["-n", "0"], 2),
            (["-s", "--capture=no"], [], 2),
        ],
    )
    def test_s_spellings_set_show_output(
        self, args: list[str], expected_cleaned: list[str], expected_verbosity: int
    ) -> None:
        """-s and its other spellings are removed and set show_output."""
        result = sanitize_extra_args(args, None)
        assert result.cleaned_args == expected_cleaned
        assert result.verbosity == expected_verbosity
        assert result.show_output is True
        assert result.notes.count(SHOW_OUTPUT_NOTE) == 1

    @pytest.mark.parametrize(
        "args",
        [
            ["-vrs"],
            ["-rfEs"],
            ["-ktest_s"],
            ["-kfoo"],
            ["-xktest_pass"],
            ["-oxfail_strict=true"],
            ["-p", "no:cacheprovider"],
            ["-n", "2"],
            ["--capture=sys"],
            ["--capture", "tee-sys"],
            ["--capture=fd"],
        ],
    )
    def test_non_switch_args_pass_through(self, args: list[str]) -> None:
        """Args that are not pure switch groups or capture=no pass through."""
        result = sanitize_extra_args(args, None)
        assert result.cleaned_args == args
        assert result.show_output is False
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
        assert result.show_output is True
        assert len(result.notes) == 2
        assert "-m flag" in result.notes[0]
        assert result.notes[1] == SHOW_OUTPUT_NOTE


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


class TestSanitizeExtraArgsPathArgs:
    """Tests for the path_args list in sanitize_extra_args."""

    def test_no_extra_args_path_args_empty(self) -> None:
        """No extra_args gives an empty path_args list."""
        assert sanitize_extra_args(None, None).path_args == []

    def test_shape_match_path_listed(self) -> None:
        """An existing path that looks like a path is listed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "tests"))
            with open(os.path.join(tmpdir, "tests", "test_x.py"), "w") as f:
                f.write("")
            result = sanitize_extra_args(
                ["-x", "tests/test_x.py::test_a"], None, project_dir=tmpdir
            )
            assert result.path_args == ["tests/test_x.py::test_a"]

    def test_bare_directory_listed(self) -> None:
        """An existing bare directory name is listed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "subdir"))
            result = sanitize_extra_args(["subdir"], None, project_dir=tmpdir)
            assert result.path_args == ["subdir"]

    def test_missing_and_absolute_paths_not_listed(self) -> None:
        """Missing and absolute paths are not listed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_path = os.path.join(tmpdir, "test_example.py")
            with open(abs_path, "w") as f:
                f.write("")
            result = sanitize_extra_args(
                ["no_such_file.py", abs_path], None, project_dir=tmpdir
            )
            assert result.path_args == []
