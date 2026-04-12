"""Tests for the black runner module."""

from unittest.mock import MagicMock, patch

from mcp_coder_utils.subprocess_runner import CommandResult

from mcp_tools_py.formatter.black_runner import run_black


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
