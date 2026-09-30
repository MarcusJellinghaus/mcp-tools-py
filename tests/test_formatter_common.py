"""Tests for the helpers shared by the formatter runners."""

import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.formatter.common import (
    MAX_LINES,
    combine_output,
    formatter_binary,
    formatter_version,
    relative_path,
    truncate_output,
    version_line,
)
from tests.conftest import make_command_result

_EXECUTE = "mcp_tools_py.formatter.common.execute_command"

# Recorded stdout of `<tool> --version` from the tool env (Windows, Python 3.11.9).
_BLACK_VERSION_STDOUT = "black, 26.5.1 (compiled: yes)\nPython (CPython) 3.11.9\n"
_ISORT_VERSION_STDOUT = (
    "\n"
    "                 _                 _\n"
    "                (_) ___  ___  _ __| |_\n"
    "                | |/ _/ / _ \\/ '__  _/\n"
    "                | |\\__ \\/\\_\\/| |  | |_\n"
    "                |_|\\___/\\___/\\_/   \\_/\n"
    "\n"
    "      isort your imports, so you don't have to.\n"
    "\n"
    "                    VERSION 9.0.2 (compiled yes)\n"
    "\n"
)
_RUFF_VERSION_STDOUT = "ruff 0.16.9\n"


def test_truncate_output_under_cap_unchanged() -> None:
    text = "\n".join(f"line {i}" for i in range(MAX_LINES))

    assert truncate_output(text) == text


def test_truncate_output_over_cap_appends_marker() -> None:
    text = "\n".join(f"line {i}" for i in range(MAX_LINES + 30))

    lines = truncate_output(text).splitlines()

    assert len(lines) == MAX_LINES + 1
    assert lines[-1] == "... (truncated, 30 more lines)"


@pytest.mark.parametrize(
    ("stdout", "stderr", "expected"),
    [
        ("out", "err", "out\nerr"),
        ("out", "", "out"),
        ("", "err", "err"),
        ("", "", ""),
    ],
)
def test_combine_output(stdout: str, stderr: str, expected: str) -> None:
    result = make_command_result(stdout=stdout, stderr=stderr)

    assert combine_output(result) == expected


def test_formatter_version_real_black() -> None:
    binary = formatter_binary("black")
    assert binary is not None

    version = formatter_version(binary, 30)

    assert re.fullmatch(r"\d+(\.\d+)+", version)


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        (_BLACK_VERSION_STDOUT, "26.5.1"),
        (_ISORT_VERSION_STDOUT, "9.0.2"),
        (_RUFF_VERSION_STDOUT, "0.16.9"),
    ],
)
@patch(_EXECUTE)
def test_formatter_version_parses_recorded_output(
    mock_exec: MagicMock, stdout: str, expected: str
) -> None:
    mock_exec.return_value = make_command_result(stdout=stdout)

    assert formatter_version("/tool-env/bin/tool", 30) == expected


@pytest.mark.parametrize(
    "result",
    [
        make_command_result(timed_out=True, execution_error="timed out"),
        make_command_result(execution_error="FileNotFoundError: black"),
        make_command_result(return_code=1, stdout="black, 26.5.1"),
        make_command_result(stdout="no version here"),
    ],
    ids=["timed_out", "execution_error", "non_zero_exit", "no_match"],
)
@patch(_EXECUTE)
def test_formatter_version_degrades_to_unknown(
    mock_exec: MagicMock, result: object
) -> None:
    mock_exec.return_value = result

    assert formatter_version("/tool-env/bin/black", 30) == "unknown"


@patch(_EXECUTE)
def test_formatter_version_command_and_timeout(mock_exec: MagicMock) -> None:
    mock_exec.return_value = make_command_result(stdout=_RUFF_VERSION_STDOUT)

    formatter_version("/tool-env/bin/ruff", 7)

    mock_exec.assert_called_once()
    assert mock_exec.call_args[0][0] == ["/tool-env/bin/ruff", "--version"]
    assert mock_exec.call_args[1]["timeout_seconds"] == 7


@pytest.mark.parametrize("timeout_seconds", [0, -3])
@patch(_EXECUTE)
def test_formatter_version_no_budget_skips_subprocess(
    mock_exec: MagicMock, timeout_seconds: int
) -> None:
    assert formatter_version("/tool-env/bin/black", timeout_seconds) == "unknown"
    mock_exec.assert_not_called()


@patch(_EXECUTE)
def test_version_line(mock_exec: MagicMock) -> None:
    mock_exec.return_value = make_command_result(stdout=_RUFF_VERSION_STDOUT)

    assert version_line("ruff", "/tool-env/bin/ruff", 30) == "ruff 0.16.9"


@pytest.fixture
def _elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project dir that is not the cwd, so a missing isabs guard adds '../'."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    cwd = tmp_path / "elsewhere" / "deeper"
    cwd.mkdir(parents=True)
    monkeypatch.chdir(cwd)
    return project_dir


def test_relative_path_relative_input_unchanged_in_depth(_elsewhere: Path) -> None:
    assert relative_path(os.path.join("src", "bad.py"), str(_elsewhere)) == (
        "src/bad.py"
    )


def test_relative_path_absolute_input(_elsewhere: Path) -> None:
    path = os.path.join(str(_elsewhere), "src", "bad.py")

    assert relative_path(path, str(_elsewhere)) == "src/bad.py"
