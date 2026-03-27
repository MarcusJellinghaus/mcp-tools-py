"""Tests for CheckerTools extraction from server.py."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from tests.conftest import make_command_result


@pytest.fixture
def mock_server() -> MagicMock:
    """Create a mock CodeCheckerServer with required attributes."""
    server = MagicMock()
    server.project_dir = Path("/fake/project")
    server.test_folder = "tests"
    server.keep_temp_files = False
    server.venv_path = "/mock/venv"
    server._resolved_python = "/usr/bin/python3"
    server._lint_imports_binary = "/mock/venv/bin/lint-imports"
    server._tool_availability = {
        "pylint": True,
        "pytest": True,
        "mypy": True,
        "lint-imports": True,
        "vulture": True,
    }
    server._vulture_binary = "/mock/venv/bin/vulture"
    server.vulture_whitelist = "vulture_whitelist.py"
    return server


@pytest.fixture
def checker_tools(mock_server: MagicMock) -> CheckerTools:
    """Create a CheckerTools instance with a mock server."""
    return CheckerTools(mock_server)


# --- Registration tests ---


def test_checker_tools_registers_five_tools(mock_server: MagicMock) -> None:
    """Test that CheckerTools.register() registers exactly 5 tools on an MCP server."""
    mock_mcp = MagicMock()
    mock_decorator = MagicMock(side_effect=lambda fn: fn)
    mock_mcp.tool.return_value = mock_decorator

    checker = CheckerTools(mock_server)
    checker.register(mock_mcp)

    # 5 tools: run_pylint_check, run_pytest_check, run_mypy_check, run_lint_imports_check, run_vulture_check
    assert mock_mcp.tool.call_count == 5


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


# --- Lint-imports handler tests ---


def test_lint_imports_success_returns_raw_output(
    mock_server: MagicMock, checker_tools: CheckerTools
) -> None:
    """When lint-imports succeeds, return raw stdout."""
    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = lambda fn: fn

    checker_tools.register(mock_mcp)

    with patch(
        "mcp_tools_py.checker_tools.execute_command",
        return_value=make_command_result(
            return_code=0, stdout="Contracts: 2 kept, 0 broken"
        ),
    ):
        # Call the registered tool function directly via the instance's register
        # We need to get the function - it was registered via @mcp.tool()
        # Since mock_mcp.tool returns identity, the function is defined in scope
        # Re-register to capture
        captured_fns: dict[str, Any] = {}

        def capture(fn: Any) -> Any:
            captured_fns[fn.__name__] = fn
            return fn

        mock_mcp2 = MagicMock()
        mock_mcp2.tool.return_value = capture
        checker_tools.register(mock_mcp2)

        result = captured_fns["run_lint_imports_check"]()

    assert "Contracts: 2 kept, 0 broken" in result


def test_lint_imports_failure_returns_raw_output(
    mock_server: MagicMock, checker_tools: CheckerTools
) -> None:
    """When lint-imports fails, return raw stdout+stderr."""
    captured_fns: dict[str, Any] = {}

    def capture(fn: Any) -> Any:
        captured_fns[fn.__name__] = fn
        return fn

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture
    checker_tools.register(mock_mcp)

    with patch(
        "mcp_tools_py.checker_tools.execute_command",
        return_value=make_command_result(
            return_code=1, stderr="Could not read any configuration."
        ),
    ):
        result = captured_fns["run_lint_imports_check"]()

    assert "Could not read any configuration." in result


# --- Vulture handler tests ---


def _capture_vulture(
    mock_server: MagicMock,
) -> Any:
    """Register checker tools and capture the run_vulture_check function."""
    captured_fns: dict[str, Any] = {}

    def capture(fn: Any) -> Any:
        captured_fns[fn.__name__] = fn
        return fn

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture
    checker = CheckerTools(mock_server)
    checker.register(mock_mcp)
    return captured_fns["run_vulture_check"]


def test_vulture_unavailable_returns_error(mock_server: MagicMock) -> None:
    """When vulture is not available, return an error message."""
    mock_server._tool_availability["vulture"] = False
    run_vulture = _capture_vulture(mock_server)
    result = run_vulture()
    assert "vulture is not available" in result


def test_vulture_success_returns_raw_output(mock_server: MagicMock) -> None:
    """When vulture succeeds, return raw stdout."""
    run_vulture = _capture_vulture(mock_server)

    with patch(
        "mcp_tools_py.checker_tools.execute_command",
        return_value=make_command_result(return_code=0, stdout="No dead code found!"),
    ):
        result = run_vulture()

    assert "No dead code found!" in result


def test_vulture_failure_returns_raw_output(mock_server: MagicMock) -> None:
    """When vulture fails, return raw stdout+stderr."""
    run_vulture = _capture_vulture(mock_server)

    with patch(
        "mcp_tools_py.checker_tools.execute_command",
        return_value=make_command_result(
            return_code=1, stderr="vulture: error: invalid config"
        ),
    ):
        result = run_vulture()

    assert "vulture: error: invalid config" in result


def test_vulture_whitelist_auto_included(mock_server: MagicMock) -> None:
    """When whitelist file exists, it is appended to the command."""
    run_vulture = _capture_vulture(mock_server)

    with (
        patch(
            "mcp_tools_py.checker_tools.execute_command",
            return_value=make_command_result(return_code=0, stdout="ok"),
        ) as mock_exec,
        patch.object(Path, "exists", return_value=True),
    ):
        run_vulture()

    cmd = mock_exec.call_args[0][0]
    whitelist_str = str(Path("/fake/project") / "vulture_whitelist.py")
    assert whitelist_str in cmd


def test_vulture_default_directories(mock_server: MagicMock) -> None:
    """Verify default dirs are ["src"] (+ "tests" if exists)."""
    run_vulture = _capture_vulture(mock_server)

    with (
        patch(
            "mcp_tools_py.checker_tools.execute_command",
            return_value=make_command_result(return_code=0, stdout="ok"),
        ) as mock_exec,
        patch("mcp_tools_py.checker_tools.os.path.isdir", return_value=False),
        patch.object(Path, "exists", return_value=False),
    ):
        run_vulture()

    cmd = mock_exec.call_args[0][0]
    assert cmd[0] == "/mock/venv/bin/vulture"
    assert "src" in cmd
    assert "tests" not in cmd
