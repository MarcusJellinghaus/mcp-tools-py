"""Tests for code_checker_vulture.runners module."""

from typing import Any
from unittest.mock import patch

from mcp_tools_py.code_checker_vulture.runners import run_vulture_check
from tests.conftest import make_command_result

MODULE_PATH = "mcp_tools_py.code_checker_vulture.runners"


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_success(mock_exec: Any) -> None:
    """Mock execute_command returning stdout, verify output returned."""
    mock_exec.return_value = make_command_result(stdout="unused code found\n")

    result = run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
    )

    assert result == "unused code found"
    mock_exec.assert_called_once()
    cmd = mock_exec.call_args[0][0]
    assert cmd[0] == "/usr/bin/vulture"
    assert "src" in cmd


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_combines_stderr(mock_exec: Any) -> None:
    """Mock with both stdout and stderr, verify combined output."""
    mock_exec.return_value = make_command_result(
        stdout="unused import", stderr="warning: something"
    )

    result = run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
    )

    assert "unused import" in result
    assert "warning: something" in result


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_no_output(mock_exec: Any) -> None:
    """Mock empty output, verify fallback message returned."""
    mock_exec.return_value = make_command_result(stdout="", stderr="")

    result = run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
    )

    assert result == "vulture produced no output."


@patch(f"{MODULE_PATH}.os.path.exists", return_value=True)
@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_includes_whitelist(mock_exec: Any, _mock_exists: Any) -> None:
    """Provide whitelist_path to existing file, verify it's in command."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
        whitelist_path="/project/whitelist.py",
    )

    cmd = mock_exec.call_args[0][0]
    assert "/project/whitelist.py" in cmd


@patch(f"{MODULE_PATH}.os.path.exists", return_value=False)
@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_skips_missing_whitelist(mock_exec: Any, _mock_exists: Any) -> None:
    """Provide whitelist_path to non-existent file, verify it's NOT in command."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
        whitelist_path="/project/missing_whitelist.py",
    )

    cmd = mock_exec.call_args[0][0]
    assert "/project/missing_whitelist.py" not in cmd


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_passes_min_confidence(mock_exec: Any) -> None:
    """Verify --min-confidence and value in command."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
        min_confidence=80,
    )

    cmd = mock_exec.call_args[0][0]
    assert "--min-confidence" in cmd
    confidence_idx = cmd.index("--min-confidence")
    assert cmd[confidence_idx + 1] == "80"


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_passes_extra_args(mock_exec: Any) -> None:
    """Verify extra args appended to command."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
        extra_args=["--exclude", "migrations"],
    )

    cmd = mock_exec.call_args[0][0]
    assert "--exclude" in cmd
    assert "migrations" in cmd
