"""Tests for CheckerTools extraction from server.py."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools


@pytest.fixture
def mock_server() -> MagicMock:
    """Create a mock CodeCheckerServer with required attributes."""
    server = MagicMock()
    server.project_dir = Path("/fake/project")
    server.test_folder = "tests"
    server.keep_temp_files = False
    server.venv_path = None
    server._resolved_python = "/usr/bin/python3"
    server._tool_availability = {"pylint": True, "pytest": True, "mypy": True}
    return server


@pytest.fixture
def checker_tools(mock_server: MagicMock) -> CheckerTools:
    """Create a CheckerTools instance with a mock server."""
    return CheckerTools(mock_server)


# --- Registration tests ---


def test_checker_tools_registers_three_tools(mock_server: MagicMock) -> None:
    """Test that CheckerTools.register() registers exactly 3 tools on an MCP server."""
    mock_mcp = MagicMock()
    mock_decorator = MagicMock(side_effect=lambda fn: fn)
    mock_mcp.tool.return_value = mock_decorator

    checker = CheckerTools(mock_server)
    checker.register(mock_mcp)

    # 3 tools: run_pylint_check, run_pytest_check, run_mypy_check
    assert mock_mcp.tool.call_count == 3


# --- Pylint formatting tests ---


def test_format_pylint_result_no_issues(checker_tools: CheckerTools) -> None:
    """Test formatting when pylint finds no issues."""
    result = checker_tools._format_pylint_result(None)
    assert "No issues found" in result


def test_format_pylint_result_with_issues(checker_tools: CheckerTools) -> None:
    """Test formatting when pylint finds issues."""
    prompt = "pylint found some issues related to code W0612."
    result = checker_tools._format_pylint_result(prompt)
    assert result == prompt


# --- Mypy formatting tests ---


def test_format_mypy_result_no_issues(checker_tools: CheckerTools) -> None:
    """Test formatting when mypy finds no type errors."""
    result = checker_tools._format_mypy_result(None)
    assert "No type errors found" in result


def test_format_mypy_result_with_issues(checker_tools: CheckerTools) -> None:
    """Test formatting when mypy finds type issues."""
    prompt = "src/foo.py:10: error: Incompatible types"
    result = checker_tools._format_mypy_result(prompt)
    assert "Mypy found type issues" in result
    assert prompt in result


# --- Pytest formatting tests ---


def test_format_pytest_result_success(checker_tools: CheckerTools) -> None:
    """Test formatting for a successful pytest run."""
    test_results: dict[str, Any] = {
        "success": True,
        "summary": {
            "passed": 10,
            "failed": 0,
            "error": 0,
            "collected": 10,
            "duration": 2.3,
        },
        "test_results": None,
        "summary_text": "10 passed in 2.30s",
    }
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Pytest check completed" in result
    assert "10" in result


def test_format_pytest_result_failure(checker_tools: CheckerTools) -> None:
    """Test formatting for a failed pytest run."""
    test_results: dict[str, Any] = {
        "success": True,
        "summary": {
            "passed": 5,
            "failed": 2,
            "error": 0,
            "collected": 7,
            "duration": 1.5,
        },
        "test_results": MagicMock(),
    }
    with patch(
        "mcp_tools_py.checker_tools.create_prompt_for_failed_tests"
    ) as mock_prompt:
        mock_prompt.return_value = "Detailed failure info..."
        result = checker_tools._format_pytest_result_with_details(
            test_results, show_details=True
        )
    assert "Pytest found issues" in result
    assert "Detailed failure info..." in result


def test_format_pytest_result_execution_error(checker_tools: CheckerTools) -> None:
    """Test formatting when pytest fails to execute."""
    test_results: dict[str, Any] = {
        "success": False,
        "error": "No module named 'pytest'",
    }
    result = checker_tools._format_pytest_result_with_details(
        test_results, show_details=True
    )
    assert "Error running pytest" in result
    assert "No module named 'pytest'" in result
