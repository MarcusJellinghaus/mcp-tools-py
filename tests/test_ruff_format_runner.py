"""Tests for the ruff format runner."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.formatter import common, ruff_runner
from mcp_tools_py.formatter.ruff_runner import _FAILED_TO_PARSE, run_ruff_format
from mcp_tools_py.utils.subprocess_runner import CommandResult
from tests.conftest import make_command_result

_RUFF_BINARY = "/tool-env/bin/ruff"
_EXECUTE = "mcp_tools_py.formatter.ruff_runner.execute_command"


@pytest.fixture(autouse=True)
def _fixed_formatter_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the ruff binary, independent of the interpreter running the suite."""
    monkeypatch.setattr(
        ruff_runner, "formatter_binary", MagicMock(return_value=_RUFF_BINARY)
    )


@pytest.fixture(autouse=True)
def _fixed_version_line(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Pin the version banner so no test spawns a `--version` subprocess."""
    mock = MagicMock(return_value="ruff 0.0.0")
    monkeypatch.setattr(ruff_runner, "version_line", mock)
    return mock


def _unformatted(project_dir: Path, *parts: str) -> dict[str, object]:
    """A recorded `unformatted` diagnostic, with ruff's absolute filename."""
    return {
        "cell": None,
        "code": "unformatted",
        "end_location": {"column": 1, "row": 2},
        "filename": os.path.join(str(project_dir), *parts),
        "fix": {
            "applicability": "safe",
            "edits": [
                {
                    "content": "x = 1\n",
                    "end_location": {"column": 1, "row": 2},
                    "location": {"column": 1, "row": 1},
                }
            ],
            "message": None,
        },
        "location": {"column": 1, "row": 1},
        "message": "File would be reformatted",
        "noqa_row": None,
        "url": None,
    }


def _invalid_syntax(project_dir: Path, *parts: str) -> dict[str, object]:
    """A recorded `invalid-syntax` diagnostic, with ruff's absolute filename."""
    return {
        "cell": None,
        "code": "invalid-syntax",
        "end_location": {"column": 8, "row": 1},
        "filename": os.path.join(str(project_dir), *parts),
        "fix": None,
        "location": {"column": 7, "row": 1},
        "message": "Expected ')', found ':'",
        "noqa_row": None,
        "url": None,
    }


def _command(mock_exec: MagicMock) -> list[str]:
    return list(mock_exec.call_args[0][0])


@patch(_EXECUTE)
def test_write_mode_argv(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.return_value = make_command_result()

    run_ruff_format("/usr/bin/python", ["src"], str(tmp_path))

    assert _command(mock_exec) == [_RUFF_BINARY, "format", "src"]


@patch(_EXECUTE)
def test_check_mode_argv(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.return_value = make_command_result()

    run_ruff_format("/usr/bin/python", ["src"], str(tmp_path), check_only=True)

    assert _command(mock_exec) == [
        _RUFF_BINARY,
        "format",
        "--check",
        "--output-format",
        "json",
        "src",
    ]


@patch(_EXECUTE)
def test_ignores_python_executable(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.return_value = make_command_result()

    run_ruff_format("/usr/bin/python", ["src"], str(tmp_path))
    expected = _command(mock_exec)
    run_ruff_format("/nonexistent/python", ["src"], str(tmp_path))

    assert _command(mock_exec) == expected


@patch(_EXECUTE)
def test_write_mode_files_changed_empty(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.return_value = make_command_result(stdout="2 files reformatted\n")

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path))

    assert result.success is True
    assert result.files_changed == []
    assert "2 files reformatted" in result.output


@patch(_EXECUTE)
def test_check_mode_unformatted_to_files_changed(
    mock_exec: MagicMock, tmp_path: Path
) -> None:
    stdout = json.dumps([_unformatted(tmp_path, "src", "ugly.py")])
    mock_exec.return_value = make_command_result(return_code=1, stdout=stdout)

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path), check_only=True)

    assert result.success is False
    assert result.files_changed == ["src/ugly.py"]
    assert result.unparsable_files == []


@patch(_EXECUTE)
def test_check_mode_invalid_syntax_is_unparsable_not_changed(
    mock_exec: MagicMock, tmp_path: Path
) -> None:
    stdout = json.dumps(
        [
            _unformatted(tmp_path, "src", "ugly.py"),
            _invalid_syntax(tmp_path, "src", "bad.py"),
        ]
    )
    mock_exec.return_value = make_command_result(return_code=2, stdout=stdout)

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path), check_only=True)

    assert result.files_changed == ["src/ugly.py"]
    assert result.unparsable_files == ["src/bad.py"]


@patch(_EXECUTE)
def test_check_mode_output_is_rendered(mock_exec: MagicMock, tmp_path: Path) -> None:
    stdout = json.dumps([_unformatted(tmp_path, "src", "ugly.py")])
    mock_exec.return_value = make_command_result(return_code=1, stdout=stdout)

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path), check_only=True)

    lines = result.output.splitlines()
    assert lines[0] == "ruff 0.0.0"
    assert any("src/ugly.py" in line and "unformatted" in line for line in lines)
    assert '"filename"' not in result.output


@patch(_EXECUTE)
def test_check_mode_malformed_json(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.return_value = make_command_result(return_code=1, stdout="[not json")

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path), check_only=True)

    assert result.success is False
    assert "Failed to parse ruff JSON output" in result.output
    assert result.files_changed == []
    assert result.unparsable_files == []


@patch(_EXECUTE)
def test_write_mode_failed_to_parse_on_stderr(
    mock_exec: MagicMock, tmp_path: Path
) -> None:
    mock_exec.return_value = make_command_result(
        return_code=2,
        stdout="1 file reformatted, 1 file left unchanged\n",
        stderr="error: Failed to parse src/bad.py:1:7: Expected ')', found ':'\n",
    )

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path))

    assert result.success is False
    assert result.unparsable_files == ["src/bad.py"]


def test_failed_to_parse_keeps_drive_letter_path() -> None:
    stderr = r"error: Failed to parse C:\repo\src\bad.py:1:7: msg"

    assert _FAILED_TO_PARSE.findall(stderr) == [r"C:\repo\src\bad.py"]


@patch(_EXECUTE)
def test_config_error_exit_2(mock_exec: MagicMock, tmp_path: Path) -> None:
    stderr = "ruff failed\n  Cause: Failed to parse pyproject.toml\n"
    mock_exec.return_value = make_command_result(return_code=2, stderr=stderr)

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path))

    assert result.success is False
    assert result.unparsable_files == []
    assert "Cause: Failed to parse pyproject.toml" in result.output


@patch(_EXECUTE)
def test_check_mode_unparsable_only(mock_exec: MagicMock, tmp_path: Path) -> None:
    stdout = json.dumps([_invalid_syntax(tmp_path, "src", "bad.py")])
    mock_exec.return_value = make_command_result(return_code=2, stdout=stdout)

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path), check_only=True)

    assert result.success is False
    assert "src/bad.py" in result.unparsable_files
    assert result.files_changed == []


@patch(_EXECUTE)
def test_missing_binary(
    mock_exec: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ruff_runner, "formatter_binary", MagicMock(return_value=None))

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path))

    mock_exec.assert_not_called()
    assert result.success is False
    assert "ruff is not available" in result.output
    assert result.unparsable_files == []


@pytest.mark.parametrize(
    "command_result",
    [
        make_command_result(timed_out=True, execution_error="timed out"),
        make_command_result(execution_error="FileNotFoundError: ruff"),
    ],
    ids=["timed_out", "execution_error"],
)
@patch(_EXECUTE)
def test_failure_paths_have_no_banner(
    mock_exec: MagicMock,
    _fixed_version_line: MagicMock,
    command_result: CommandResult,
    tmp_path: Path,
) -> None:
    mock_exec.return_value = command_result

    result = run_ruff_format("/usr/bin/python", ["src"], str(tmp_path))

    _fixed_version_line.assert_not_called()
    assert result.success is False
    assert result.unparsable_files == []
    assert "ruff 0.0.0" not in result.output


def test_real_ruff_formats_other_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ruff_runner, "formatter_binary", common.formatter_binary)
    monkeypatch.setattr(ruff_runner, "version_line", common.version_line)
    src = tmp_path / "src"
    src.mkdir()
    ugly = src / "ugly.py"
    ugly.write_text("x=1\n", encoding="utf-8")
    (src / "bad.py").write_text("def f(:\n", encoding="utf-8")

    result = run_ruff_format("/nonexistent/python", ["src"], str(tmp_path))

    assert ugly.read_text(encoding="utf-8") == "x = 1\n"
    assert result.unparsable_files == ["src/bad.py"]
    assert result.success is False
