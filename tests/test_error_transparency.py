"""Tests for error transparency: stderr surfacing and 'No module named' detection."""

import sys
from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_mypy.runners import run_mypy_check
from mcp_tools_py.code_checker_pylint.runners import get_pylint_results
from mcp_tools_py.code_checker_pytest.runners import run_tests
from mcp_tools_py.utils.subprocess_runner import (
    MAX_STDERR_IN_ERROR,
    check_tool_missing_error,
    truncate_stderr,
)
from tests.conftest import make_command_result

# ---------------------------------------------------------------------------
# Unit tests for shared helpers
# ---------------------------------------------------------------------------


class TestCheckToolMissingError:
    """Tests for check_tool_missing_error helper."""

    def test_detects_missing_module(self) -> None:
        stderr = "No module named pytest"
        result = check_tool_missing_error(stderr, "pytest", "/usr/bin/python")
        assert result is not None
        assert "pytest is not installed" in result
        assert "/usr/bin/python" in result

    def test_returns_none_when_no_match(self) -> None:
        stderr = "Some other error occurred"
        result = check_tool_missing_error(stderr, "pytest", "/usr/bin/python")
        assert result is None

    def test_returns_none_for_empty_stderr(self) -> None:
        result = check_tool_missing_error("", "pytest", "/usr/bin/python")
        assert result is None


class TestTruncateStderr:
    """Tests for truncate_stderr helper."""

    def test_long_stderr_truncated(self) -> None:
        long_stderr = "x" * (MAX_STDERR_IN_ERROR + 100)
        result = truncate_stderr(long_stderr)
        assert len(result) == MAX_STDERR_IN_ERROR + 3  # +3 for "..."
        assert result.endswith("...")

    def test_short_stderr_not_truncated(self) -> None:
        short_stderr = "short error"
        result = truncate_stderr(short_stderr)
        assert result == short_stderr
        assert not result.endswith("...")

    def test_exact_limit_not_truncated(self) -> None:
        exact_stderr = "x" * MAX_STDERR_IN_ERROR
        result = truncate_stderr(exact_stderr)
        assert result == exact_stderr
        assert not result.endswith("...")


# ---------------------------------------------------------------------------
# Pytest runner error transparency
# ---------------------------------------------------------------------------


class TestPytestNoModuleDetection:
    """Test that 'No module named pytest' in stderr produces actionable error."""

    @patch("mcp_tools_py.code_checker_pytest.runners.execute_command")
    def test_no_module_pytest_detected(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=1,
            stderr="No module named pytest",
        )
        with pytest.raises(RuntimeError, match="pytest is not installed"):
            run_tests(
                project_dir=".", test_folder="tests", python_executable=sys.executable
            )

    @patch("mcp_tools_py.code_checker_pytest.runners.execute_command")
    def test_stderr_surfaced_on_generic_failure(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=1,
            stderr="some unexpected error from subprocess",
        )
        with pytest.raises(RuntimeError, match="some unexpected error"):
            run_tests(
                project_dir=".", test_folder="tests", python_executable=sys.executable
            )


# ---------------------------------------------------------------------------
# Pylint runner error transparency
# ---------------------------------------------------------------------------


class TestPylintNoModuleDetection:
    """Test that 'No module named pylint' in stderr produces actionable error."""

    @patch("mcp_tools_py.code_checker_pylint.runners.execute_command")
    def test_no_module_pylint_detected(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=1,
            stderr="No module named pylint",
            execution_error="ModuleNotFoundError: No module named 'pylint'",
        )
        result = get_pylint_results(project_dir=".", python_executable=sys.executable)
        assert result.error is not None
        assert "pylint is not installed" in result.error

    @patch("mcp_tools_py.code_checker_pylint.runners.execute_command")
    def test_stderr_appended_to_execution_error(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=1,
            stderr="some pylint subprocess error",
            execution_error="Command failed",
        )
        result = get_pylint_results(project_dir=".", python_executable=sys.executable)
        assert result.error is not None
        assert "Command failed" in result.error
        assert "some pylint subprocess error" in result.error


# ---------------------------------------------------------------------------
# Mypy runner error transparency
# ---------------------------------------------------------------------------


class TestMypyNoModuleDetection:
    """Test that 'No module named mypy' in stderr produces actionable error."""

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_no_module_mypy_detected(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=1,
            stderr="No module named mypy",
            execution_error="ModuleNotFoundError: No module named 'mypy'",
        )
        result = run_mypy_check(project_dir=".", python_executable=sys.executable)
        assert result.error is not None
        assert "mypy is not installed" in result.error

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_stderr_appended_to_execution_error(self, mock_exec: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=1,
            stderr="some mypy subprocess error",
            execution_error="Command failed",
        )
        result = run_mypy_check(project_dir=".", python_executable=sys.executable)
        assert result.error is not None
        assert "Command failed" in result.error
        assert "some mypy subprocess error" in result.error
