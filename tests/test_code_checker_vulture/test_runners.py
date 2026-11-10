"""Tests for code_checker_vulture.runners module."""

from typing import Any
from unittest.mock import patch

from mcp_tools_py.code_checker_vulture.runners import VultureResult, run_vulture_check
from tests.conftest import make_command_result

MODULE_PATH = "mcp_tools_py.code_checker_vulture.runners"


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_success(mock_exec: Any) -> None:
    """Mock execute_command returning stdout, verify it is parsed."""
    mock_exec.return_value = make_command_result(
        stdout="src/a.py:3: unused function 'foo' (60% confidence)\n"
    )

    result = run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
    )

    assert result.error is None
    assert [(m.file, m.line, m.name) for m in result.messages] == [
        ("src/a.py", 3, "foo")
    ]
    assert result.unparsed == []
    mock_exec.assert_called_once()
    cmd = mock_exec.call_args[0][0]
    assert cmd[0] == "/usr/bin/vulture"
    assert "src" in cmd


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_combines_stderr(mock_exec: Any) -> None:
    """Mock with both stdout and stderr, verify both are parsed."""
    mock_exec.return_value = make_command_result(
        stdout="src/a.py:1: unused import 'os' (90% confidence)",
        stderr="warning: something",
    )

    result = run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
    )

    assert [m.name for m in result.messages] == ["os"]
    assert result.unparsed == ["warning: something"]


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_no_output(mock_exec: Any) -> None:
    """Mock empty output, verify an empty result."""
    mock_exec.return_value = make_command_result(stdout="", stderr="")

    result = run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
    )

    assert result == VultureResult(error=None, messages=[], unparsed=[])


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


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_timeout_reports_timeout(mock_exec: Any) -> None:
    """A killed run reports the timeout, not a false 'no output'."""
    mock_exec.return_value = make_command_result(
        timed_out=True, execution_error="Process timed out after 45 seconds"
    )

    result = run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
        timeout_seconds=45,
    )

    assert result.error == "vulture timed out after 45 seconds."
    assert result.messages == []


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_execution_error_reports_failure(mock_exec: Any) -> None:
    """An execution error is reported instead of a false 'no output'."""
    mock_exec.return_value = make_command_result(
        timed_out=False, execution_error="PermissionError: vulture"
    )

    result = run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
    )

    assert result.error == "vulture failed to run: PermissionError: vulture"
    assert result.messages == []


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_forwards_timeout_seconds(mock_exec: Any) -> None:
    """The configured timeout reaches execute_command."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
        timeout_seconds=45,
    )

    assert mock_exec.call_args.kwargs["timeout_seconds"] == 45


@patch(f"{MODULE_PATH}.execute_command")
def test_run_vulture_default_timeout_seconds(mock_exec: Any) -> None:
    """Without an explicit value the shared default is used."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_vulture_check(
        vulture_binary="/usr/bin/vulture",
        project_dir="/project",
        target_directories=["src"],
    )

    assert mock_exec.call_args.kwargs["timeout_seconds"] == 120
