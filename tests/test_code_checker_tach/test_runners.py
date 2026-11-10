"""Tests for code_checker_tach.runners module."""

from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_tach.runners import TachResult, run_tach_check
from tests.conftest import make_command_result
from tests.test_code_checker_tach.test_parsers import (
    CONFIG_ERROR_TEXT,
    VIOLATIONS_JSON,
)

MODULE_PATH = "mcp_tools_py.code_checker_tach.runners"


@pytest.mark.parametrize(
    ("return_code", "stdout", "stderr", "raw"),
    [
        (0, '{"errors": []}\n', "", '{"errors": []}'),
        (0, "", "warning: deprecated", "warning: deprecated"),
        (1, CONFIG_ERROR_TEXT, "", CONFIG_ERROR_TEXT.strip()),
        (1, "not json", "error: bad config", "not json\nerror: bad config"),
    ],
)
@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_unparsed_output_is_raw(
    mock_exec: Any, return_code: int, stdout: str, stderr: str, raw: str
) -> None:
    """Output that is not tach's JSON is kept, combined, in `raw`."""
    mock_exec.return_value = make_command_result(
        return_code=return_code, stdout=stdout, stderr=stderr
    )

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert result == TachResult(None, return_code, [], raw)


@pytest.mark.parametrize("return_code", [0, 1])
@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_no_output(mock_exec: Any, return_code: int) -> None:
    """No output parses to no diagnostics and keeps the exit code."""
    mock_exec.return_value = make_command_result(return_code=return_code)

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert result == TachResult(None, return_code, [], None)


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_parses_json(mock_exec: Any) -> None:
    """tach's JSON parses into diagnostics."""
    mock_exec.return_value = make_command_result(return_code=1, stdout=VIOLATIONS_JSON)

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert result.raw is None
    assert result.return_code == 1
    assert [d.severity for d in result.diagnostics] == ["error", "error", "warning"]


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

    assert result.error == "tach check timed out after 45 seconds."


@patch(f"{MODULE_PATH}.execute_command")
def test_run_tach_execution_error_reports_failure(mock_exec: Any) -> None:
    """An execution error is reported instead of a false pass."""
    mock_exec.return_value = make_command_result(
        timed_out=False, execution_error="FileNotFoundError: tach"
    )

    result = run_tach_check(tach_binary="/usr/bin/tach", project_dir="/project")

    assert result.error == "tach check failed to run: FileNotFoundError: tach"


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
