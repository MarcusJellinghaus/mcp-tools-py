"""Tests for code_checker_tach.runners module."""

from typing import Any
from unittest.mock import patch

from mcp_tools_py.code_checker_tach.runners import run_tach_check
from tests.conftest import make_command_result

MODULE_PATH = "mcp_tools_py.code_checker_tach.runners"


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_success_returns_status_line_and_json(mock_exec: Any) -> None:
    """Mock execute_command returning JSON stdout, verify status prefix added."""
    mock_exec.return_value = make_command_result(stdout='{"errors": []}\n')

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert result == 'tach check completed:\n{"errors": []}'


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_combines_stderr(mock_exec: Any) -> None:
    """Mock with both stdout and stderr, verify combined output."""
    mock_exec.return_value = make_command_result(
        stdout='{"errors": []}', stderr="warning: deprecated"
    )

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert result.startswith("tach check completed:\n")
    assert '{"errors": []}' in result
    assert "warning: deprecated" in result


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_stderr_only(mock_exec: Any) -> None:
    """Mock empty stdout but stderr present, verify stderr in output."""
    mock_exec.return_value = make_command_result(stdout="", stderr="error: bad config")

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert result == "tach check completed:\nerror: bad config"


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_empty_output_fallback(mock_exec: Any) -> None:
    """Mock empty stdout/stderr, verify fallback message returned."""
    mock_exec.return_value = make_command_result(stdout="", stderr="")

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert result == "tach check passed (no output)."


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_command_construction(mock_exec: Any) -> None:
    """Verify the command and cwd passed to execute_command."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    mock_exec.assert_called_once()
    cmd = mock_exec.call_args[0][0]
    assert cmd == ["/usr/bin/tach", "check", "--output", "json"]
    assert mock_exec.call_args.kwargs["cwd"] == "/project"


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_timeout_reports_timeout(mock_exec: Any) -> None:
    """A killed run reports the timeout, not a false pass."""
    mock_exec.return_value = make_command_result(
        timed_out=True, execution_error="Process timed out after 45 seconds"
    )

    result = run_tach_check(
        tach_binary="/usr/bin/tach", project_dir="/project", timeout_seconds=45
    )

    assert "timed out" in result
    assert "45" in result
    assert "passed" not in result


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_execution_error_reports_failure(mock_exec: Any) -> None:
    """An execution error is reported instead of a false pass."""
    mock_exec.return_value = make_command_result(
        timed_out=False, execution_error="FileNotFoundError: tach"
    )

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert "FileNotFoundError: tach" in result
    assert "passed" not in result


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_forwards_timeout_seconds(mock_exec: Any) -> None:
    """The configured timeout reaches execute_command."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_tach_check(
        tach_binary="/usr/bin/tach", project_dir="/project", timeout_seconds=45
    )

    assert mock_exec.call_args.kwargs["timeout_seconds"] == 45


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_default_timeout_seconds(mock_exec: Any) -> None:
    """Without an explicit value the shared default is used."""
    mock_exec.return_value = make_command_result(stdout="output")

    run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert mock_exec.call_args.kwargs["timeout_seconds"] == 120
