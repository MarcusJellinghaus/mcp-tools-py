"""Tests for test_folder=None in run_tests and check_code_with_pytest."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.code_checker_pytest import (
    PytestReport,
    check_code_with_pytest,
    run_tests,
)
from mcp_tools_py.code_checker_pytest.models import Summary
from mcp_tools_py.code_checker_pytest.verdict import RunStatus


def _write_testpaths(project: Path, testpaths: str) -> None:
    """Write a pyproject.toml with the given testpaths."""
    (project / "pyproject.toml").write_text(
        f"[tool.pytest.ini_options]\ntestpaths = {testpaths}\n", encoding="utf-8"
    )


def _no_tests_result() -> MagicMock:
    """A command result for pytest exiting with 5 (no tests collected)."""
    result = MagicMock()
    result.return_code = 5
    result.stdout = "collected 0 items"
    result.stderr = ""
    result.execution_error = None
    result.timed_out = False
    return result


def _command_of(mock_execute: MagicMock) -> list[str]:
    """The pytest command passed to execute_command."""
    command: list[str] = mock_execute.call_args.kwargs["command"]
    return command


def _passed_report() -> PytestReport:
    """A report of one passed test."""
    return PytestReport(
        created=0.0,
        duration=0.1,
        exitcode=0,
        root="/project",
        environment={},
        summary=Summary(collected=1, total=1, passed=1),
    )


class TestRunTestsNone:
    """Test the paths run_tests adds for test_folder=None."""

    @patch("mcp_tools_py.code_checker_pytest.runners.execute_command")
    def test_adds_every_testpaths_entry(
        self, mock_execute: MagicMock, tmp_path: Path
    ) -> None:
        """Both testpaths entries are in the command."""
        _write_testpaths(tmp_path, '["tests", "integration"]')
        (tmp_path / "tests").mkdir()
        (tmp_path / "integration").mkdir()
        mock_execute.return_value = _no_tests_result()

        with pytest.raises(ValueError, match="No Tests Found"):
            run_tests(str(tmp_path), None, python_executable=sys.executable)

        command = _command_of(mock_execute)
        assert os.path.join(str(tmp_path), "tests") in command
        assert os.path.join(str(tmp_path), "integration") in command

    @patch("mcp_tools_py.code_checker_pytest.runners.execute_command")
    def test_skip_default_test_folder_adds_none(
        self, mock_execute: MagicMock, tmp_path: Path
    ) -> None:
        """skip_default_test_folder=True adds no testpaths entry."""
        _write_testpaths(tmp_path, '["tests", "integration"]')
        (tmp_path / "tests").mkdir()
        (tmp_path / "integration").mkdir()
        mock_execute.return_value = _no_tests_result()

        with pytest.raises(ValueError, match="No Tests Found"):
            run_tests(
                str(tmp_path),
                None,
                python_executable=sys.executable,
                skip_default_test_folder=True,
            )

        command = _command_of(mock_execute)
        assert os.path.join(str(tmp_path), "tests") not in command
        assert os.path.join(str(tmp_path), "integration") not in command


class TestCheckCodeWithPytestNote:
    """Test the test_paths_note of check_code_with_pytest."""

    @patch("mcp_tools_py.code_checker_pytest.runners.run_tests")
    def test_note_names_missing_entry(
        self, mock_run_tests: MagicMock, tmp_path: Path
    ) -> None:
        """A missing testpaths entry is named in the note of a passing run."""
        _write_testpaths(tmp_path, '["nope"]')
        mock_run_tests.return_value = _passed_report()

        result = check_code_with_pytest(
            str(tmp_path), python_executable=sys.executable, test_folder=None
        )

        assert result["verdict"].status is RunStatus.PASSED
        assert "nope" in result["test_paths_note"]

    @patch("mcp_tools_py.code_checker_pytest.runners.run_tests")
    def test_note_survives_an_error(
        self, mock_run_tests: MagicMock, tmp_path: Path
    ) -> None:
        """When run_tests raises, the verdict is ERROR and the note is kept."""
        _write_testpaths(tmp_path, '["nope"]')
        mock_run_tests.side_effect = RuntimeError("boom")

        result = check_code_with_pytest(
            str(tmp_path), python_executable=sys.executable, test_folder=None
        )

        assert result["verdict"].status is RunStatus.ERROR
        assert "nope" in result["test_paths_note"]

    @patch("mcp_tools_py.code_checker_pytest.runners.run_tests")
    def test_skip_default_test_folder_has_no_note(
        self, mock_run_tests: MagicMock, tmp_path: Path
    ) -> None:
        """Paths from the caller mean testpaths isn't read, so no note."""
        _write_testpaths(tmp_path, '["nope"]')
        mock_run_tests.return_value = _passed_report()

        result = check_code_with_pytest(
            str(tmp_path),
            python_executable=sys.executable,
            test_folder=None,
            skip_default_test_folder=True,
        )

        assert result["test_paths_note"] is None

    def test_invalid_pyproject_is_an_error(self, tmp_path: Path) -> None:
        """Invalid TOML gives an ERROR verdict naming it."""
        (tmp_path / "pyproject.toml").write_text("invalid {{{{", encoding="utf-8")

        result = check_code_with_pytest(
            str(tmp_path), python_executable=sys.executable, test_folder=None
        )

        assert result["verdict"].status is RunStatus.ERROR
        assert any("Invalid pyproject.toml" in p for p in result["verdict"].problems)
