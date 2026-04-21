"""Tests for the isort runner module."""

from unittest.mock import MagicMock, patch

from mcp_tools_py.formatter.isort_runner import run_isort
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


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_success(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(stdout="Fixing imports")

    result = run_isort("/usr/bin/python", ["src"], "/project")

    assert result.success is True
    assert "Fixing imports" in result.output


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_check_only_flag(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result()

    run_isort("/usr/bin/python", ["src"], "/project", check_only=True)

    args = mock_exec.call_args
    command = args[1]["command"] if "command" in args[1] else args[0][0]
    assert "--check-only" in command


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_normal_mode_no_check_flag(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result()

    run_isort("/usr/bin/python", ["src"], "/project", check_only=False)

    args = mock_exec.call_args
    command = args[1]["command"] if "command" in args[1] else args[0][0]
    assert "--check-only" not in command


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_failure(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        return_code=1, stderr="ERROR: imports are incorrectly sorted"
    )

    result = run_isort("/usr/bin/python", ["src"], "/project")

    assert result.success is False
    assert "incorrectly sorted" in result.output


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_truncates_output(mock_exec: MagicMock) -> None:
    long_stdout = "\n".join(f"line {i}" for i in range(250))
    mock_exec.return_value = _make_result(stdout=long_stdout)

    result = run_isort("/usr/bin/python", ["src"], "/project")

    lines = result.output.splitlines()
    assert len(lines) == 201  # 200 lines + truncation notice
    assert "truncated" in lines[-1]
    assert "50 more lines" in lines[-1]


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_combines_stdout_stderr(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        stdout="Fixing file.py", stderr="warning: something"
    )

    result = run_isort("/usr/bin/python", ["src"], "/project")

    assert "Fixing file.py" in result.output
    assert "warning: something" in result.output


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_parses_fixing_files(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        stdout="Fixing src/foo.py",
    )

    result = run_isort("/usr/bin/python", ["src"], "/project")

    assert result.files_changed == ["src/foo.py"]


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_parses_check_mode_errors(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        return_code=1,
        stderr="ERROR: src/foo.py Imports are incorrectly sorted and/or formatted.",
    )

    result = run_isort("/usr/bin/python", ["src"], "/project", check_only=True)

    assert result.files_changed == ["src/foo.py"]


@patch("mcp_tools_py.formatter.isort_runner.execute_command")
def test_run_isort_no_files_changed(mock_exec: MagicMock) -> None:
    mock_exec.return_value = _make_result(
        stdout="Skipping file as it has already been sorted.",
    )

    result = run_isort("/usr/bin/python", ["src"], "/project")

    assert result.files_changed == []
