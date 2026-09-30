"""Tests for the black runner module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.formatter import black_runner, common
from mcp_tools_py.formatter.black_runner import run_black
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import CommandResult
from tests.conftest import make_command_result
from tests.test_tool_availability._helpers import _dummy_python

_BLACK_BINARY = "/tool-env/bin/black"


@pytest.fixture(autouse=True)
def _fixed_formatter_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the black binary, independent of the interpreter running the suite."""
    monkeypatch.setattr(
        black_runner, "formatter_binary", MagicMock(return_value=_BLACK_BINARY)
    )


def _make_result(
    return_code: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> CommandResult:
    """Create a CommandResult for testing."""
    return CommandResult(
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=False,
    )


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_success(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(stdout="All done! ✨ 🍰 ✨")

    result = run_black("/usr/bin/python", ["src"], "/project")

    assert result.success is True
    assert "All done!" in result.output


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_check_only_flag(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result()

    run_black("/usr/bin/python", ["src"], "/project", check_only=True)

    args = mock_exec.call_args
    command = args[1]["command"] if "command" in args[1] else args[0][0]
    assert "--check" in command


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_normal_mode_no_check_flag(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result()

    run_black("/usr/bin/python", ["src"], "/project", check_only=False)

    args = mock_exec.call_args
    command = args[1]["command"] if "command" in args[1] else args[0][0]
    assert "--check" not in command


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_failure(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        return_code=1, stderr="error: cannot format file.py"
    )

    result = run_black("/usr/bin/python", ["src"], "/project")

    assert result.success is False
    assert "cannot format" in result.output


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_truncates_output(mock_exec: MagicMock) -> None:
    long_stdout = "\n".join(f"line {i}" for i in range(250))
    mock_exec.return_value = _make_result(stdout=long_stdout)

    result = run_black("/usr/bin/python", ["src"], "/project")

    lines = result.output.splitlines()
    assert len(lines) == 201  # 200 lines + truncation notice
    assert "truncated" in lines[-1]
    assert "50 more lines" in lines[-1]


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_combines_stdout_stderr(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        stdout="reformatted file.py", stderr="warning: something"
    )

    result = run_black("/usr/bin/python", ["src"], "/project")

    assert "reformatted file.py" in result.output
    assert "warning: something" in result.output


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_parses_reformatted_files(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        stderr="reformatted src/foo.py\nAll done! 1 file reformatted.",
    )

    result = run_black("/usr/bin/python", ["src"], "/project")

    assert result.files_changed == ["src/foo.py"]


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_parses_would_reformat_files(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        return_code=1,
        stderr="would reformat src/foo.py\nOh no! 1 file would be reformatted.",
    )

    result = run_black("/usr/bin/python", ["src"], "/project", check_only=True)

    assert result.files_changed == ["src/foo.py"]


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_no_files_changed(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        stderr="All done! ✨ 🍰 ✨\n1 file left unchanged.",
    )

    result = run_black("/usr/bin/python", ["src"], "/project")

    assert result.files_changed == []


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_timeout_reports_reason(mock_exec: MagicMock) -> None:
    mock_exec.return_value = make_command_result(
        timed_out=True,
        execution_error="Process timed out after 5 seconds",
    )

    result = run_black("/usr/bin/python", ["src"], "/project", False, 5)

    assert result.success is False
    assert "timed out" in result.output
    assert "5" in result.output
    assert result.files_changed == []


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_execution_error_reports_reason(mock_exec: MagicMock) -> None:
    mock_exec.return_value = make_command_result(
        execution_error="FileNotFoundError: black",
    )

    result = run_black("/usr/bin/python", ["src"], "/project")

    assert result.success is False
    assert "FileNotFoundError: black" in result.output
    assert result.files_changed == []


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_forwards_timeout(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result()

    run_black("/usr/bin/python", ["src"], "/project", False, 45)

    assert mock_exec.call_args[1]["timeout_seconds"] == 45


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_default_timeout(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result()

    run_black("/usr/bin/python", ["src"], "/project")

    assert mock_exec.call_args[1]["timeout_seconds"] == 120


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_invokes_console_script(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result()

    run_black("/usr/bin/python", ["src"], "/project")

    command = mock_exec.call_args[0][0]
    assert command == [_BLACK_BINARY, "src"]
    assert "-m" not in command


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_ignores_python_executable(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result()

    run_black("/usr/bin/python", ["src"], "/project")
    expected = mock_exec.call_args[0][0]
    run_black("/nonexistent/python", ["src"], "/project")

    assert mock_exec.call_args[0][0] == expected


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_missing_binary(
    mock_exec: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(black_runner, "formatter_binary", MagicMock(return_value=None))

    result = run_black("/usr/bin/python", ["src"], "/project")

    mock_exec.assert_not_called()
    assert result.success is False
    assert "black is not available" in result.output
    assert result.files_changed == []


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_uses_injected_environment(
    mock_exec: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(black_runner, "formatter_binary", common.formatter_binary)
    mock_exec.return_value = _make_result()
    environment = PythonEnvironment(Path(_dummy_python(tmp_path, "black")))

    run_black("/usr/bin/python", ["src"], "/project", environment=environment)

    expected = environment.binary("black")
    assert expected is not None
    assert mock_exec.call_args[0][0][0] == str(expected)
