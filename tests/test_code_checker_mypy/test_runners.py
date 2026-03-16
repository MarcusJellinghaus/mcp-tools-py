"""Test mypy runner functionality."""

import sys

import pytest

from mcp_tools_py.code_checker_mypy import run_mypy_check


def test_run_mypy_check_on_project() -> None:
    """Test running mypy on the actual project."""
    result = run_mypy_check(
        project_dir=".",
        python_executable=sys.executable,
        strict=True,
        target_directories=["src"],
    )

    # 0=no errors, 1=errors found, 2=config error (should be fixed now)
    assert result.return_code in [
        0,
        1,
    ], f"Unexpected return code {result.return_code}. Error: {result.error}, Raw output: {result.raw_output}"
    assert isinstance(result.messages, list)


def test_run_mypy_check_non_existent_directory() -> None:
    """Test running mypy on a non-existent directory."""
    with pytest.raises(FileNotFoundError, match="Project directory not found"):
        run_mypy_check(
            project_dir="/non/existent/directory", python_executable=sys.executable
        )


def test_run_mypy_check_with_disabled_codes() -> None:
    """Test running mypy with disabled error codes."""
    result = run_mypy_check(
        project_dir=".",
        python_executable=sys.executable,
        strict=True,
        disable_error_codes=["import", "arg-type"],
        target_directories=["src"],
    )

    assert result.return_code in [
        0,
        1,
    ], f"Unexpected return code {result.return_code}. Error: {result.error}, Raw output: {result.raw_output}"
    # Verify that disabled codes are not in the results
    for msg in result.messages:
        if msg.code:
            assert msg.code not in ["import", "arg-type"]
