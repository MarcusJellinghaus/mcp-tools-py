"""Tests for the black runner module."""

from unittest.mock import MagicMock, patch

from mcp_tools_py.formatter.black_runner import run_black
from mcp_tools_py.utils.subprocess_runner import CommandResult


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

    output, success = run_black("/usr/bin/python", ["src"], "/project")

    assert success is True
    assert "All done!" in output


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

    output, success = run_black("/usr/bin/python", ["src"], "/project")

    assert success is False
    assert "cannot format" in output


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_truncates_output(mock_exec: MagicMock) -> None:
    long_stdout = "\n".join(f"line {i}" for i in range(250))
    mock_exec.return_value = _make_result(stdout=long_stdout)

    output, _ = run_black("/usr/bin/python", ["src"], "/project")

    lines = output.splitlines()
    assert len(lines) == 201  # 200 lines + truncation notice
    assert "truncated" in lines[-1]
    assert "50 more lines" in lines[-1]


@patch("mcp_tools_py.formatter.black_runner.execute_command")
def test_run_black_combines_stdout_stderr(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        stdout="reformatted file.py", stderr="warning: something"
    )

    output, _ = run_black("/usr/bin/python", ["src"], "/project")

    assert "reformatted file.py" in output
    assert "warning: something" in output
