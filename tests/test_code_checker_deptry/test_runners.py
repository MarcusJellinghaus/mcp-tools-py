"""Tests for code_checker_deptry.runners module."""

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_deptry.runners import (
    DeptryMessage,
    parse_deptry_json_output,
    run_deptry_check_impl,
)
from tests.conftest import make_command_result

MODULE_PATH = "mcp_tools_py.code_checker_deptry.runners"
PYTHON = "/venv/bin/python"


def _entry(
    code: str = "DEP001",
    message: str = "'foo' imported but missing from the dependency definitions",
    module: str = "foo",
    file: str = "src/pkg/a.py",
    line: int | None = 3,
    column: int | None = 8,
) -> dict[str, Any]:
    """Build one deptry JSON entry."""
    return {
        "error": {"code": code, "message": message},
        "module": module,
        "location": {"file": file, "line": line, "column": column},
    }


class TestParseDeptryJsonOutput:
    """Tests for parse_deptry_json_output."""

    def test_valid_list(self) -> None:
        messages, error = parse_deptry_json_output(json.dumps([_entry()]))

        assert error is None
        assert messages == [
            DeptryMessage(
                code="DEP001",
                message="'foo' imported but missing from the dependency definitions",
                module="foo",
                file="src/pkg/a.py",
                line=3,
                column=8,
            )
        ]

    def test_dep002_null_location(self) -> None:
        content = json.dumps(
            [
                _entry(
                    code="DEP002",
                    message="'bar' defined as a dependency but not used",
                    module="bar",
                    file="pyproject.toml",
                    line=None,
                    column=None,
                )
            ]
        )

        messages, error = parse_deptry_json_output(content)

        assert error is None
        assert messages[0].file == "pyproject.toml"
        assert messages[0].line is None
        assert messages[0].column is None

    def test_empty_list(self) -> None:
        assert parse_deptry_json_output("[]") == ([], None)

    def test_invalid_json(self) -> None:
        messages, error = parse_deptry_json_output("{not json")

        assert messages == []
        assert error is not None
        assert error.startswith("Could not parse deptry JSON output:")

    def test_non_list(self) -> None:
        messages, error = parse_deptry_json_output('{"error": "x"}')

        assert messages == []
        assert error is not None
        assert error.startswith("Could not parse deptry JSON output:")

    def test_missing_key(self) -> None:
        entry = _entry()
        del entry["module"]

        messages, error = parse_deptry_json_output(json.dumps([entry]))

        assert messages == []
        assert error is not None
        assert error.startswith("Could not parse deptry JSON output:")

    @pytest.mark.parametrize(
        "entry",
        [
            _entry(line="3"),  # type: ignore[arg-type]
            _entry(column=1.5),  # type: ignore[arg-type]
            _entry(module=7),  # type: ignore[arg-type]
            _entry(code=None),  # type: ignore[arg-type]
            "not a dict",
        ],
    )
    def test_wrong_type(self, entry: Any) -> None:
        messages, error = parse_deptry_json_output(json.dumps([entry]))

        assert messages == []
        assert error is not None
        assert error.startswith("Could not parse deptry JSON output:")


def _writing_side_effect(output: str | None, return_code: int, stderr: str = "") -> Any:
    """Build an execute_command side_effect writing ``output`` to --json-output."""

    def _write(
        cmd: list[str], cwd: str | None = None, timeout_seconds: int | None = None
    ) -> Any:
        del cwd, timeout_seconds
        if output is not None:
            out = cmd[cmd.index("--json-output") + 1]
            Path(out).write_text(output, encoding="utf-8")
        return make_command_result(return_code=return_code, stderr=stderr)

    return _write


def _output_path(cmd: list[str]) -> str:
    """Return the path passed to --json-output."""
    return cmd[cmd.index("--json-output") + 1]


class TestRunDeptryCheckImpl:
    """Tests for run_deptry_check_impl."""

    @patch(f"{MODULE_PATH}.execute_command")
    def test_command(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.side_effect = _writing_side_effect("[]", return_code=0)

        run_deptry_check_impl(
            PYTHON,
            str(tmp_path),
            ["src", "lib"],
            extra_args=["--config", "other.toml"],
            timeout_seconds=45,
        )

        cmd = mock_exec.call_args.args[0]
        assert cmd[:5] == [PYTHON, "-m", "deptry", "src", "lib"]
        assert cmd[5] == "--json-output"
        assert os.path.basename(os.path.dirname(cmd[6])).startswith("deptry_runner_")
        assert cmd[7:] == ["--config", "other.toml"]
        assert mock_exec.call_args.kwargs["cwd"] == str(tmp_path)
        assert mock_exec.call_args.kwargs["timeout_seconds"] == 45

    @patch(f"{MODULE_PATH}.execute_command")
    def test_clean(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.side_effect = _writing_side_effect("[]", return_code=0)

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.return_code == 0
        assert result.messages == []
        assert result.error is None
        assert result.raw_output == "[]"

    @patch(f"{MODULE_PATH}.execute_command")
    def test_findings(self, mock_exec: Any, tmp_path: Path) -> None:
        content = json.dumps([_entry(), _entry(code="DEP003", module="baz")])
        mock_exec.side_effect = _writing_side_effect(content, return_code=1)

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.return_code == 1
        assert [m.code for m in result.messages] == ["DEP001", "DEP003"]
        assert result.error is None
        assert result.raw_output == content

    @patch(f"{MODULE_PATH}.execute_command")
    def test_exit_1_without_file_is_error(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.side_effect = _writing_side_effect(
            None, return_code=1, stderr="Traceback: boom"
        )

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.messages == []
        assert result.error is not None
        assert "no JSON output file" in result.error
        assert "exit code 1" in result.error
        assert "boom" in result.error

    @patch(f"{MODULE_PATH}.execute_command")
    def test_empty_file_is_error(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.side_effect = _writing_side_effect("", return_code=0)

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.messages == []
        assert result.error == "deptry produced no JSON output file (exit code 0)"

    @patch(f"{MODULE_PATH}.execute_command")
    def test_exit_2_is_error(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.return_value = make_command_result(
            return_code=2, stderr="Error: No such option: --bogus\n"
        )

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.return_code == 2
        assert result.messages == []
        assert result.error == (
            "deptry exited with code 2: Error: No such option: --bogus"
        )

    @patch(f"{MODULE_PATH}.execute_command")
    def test_unparsable_file_is_error(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.side_effect = _writing_side_effect("{oops", return_code=1)

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.messages == []
        assert result.error is not None
        assert result.error.startswith("Could not parse deptry JSON output:")

    @patch(f"{MODULE_PATH}.execute_command")
    def test_timeout(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.return_value = make_command_result(
            timed_out=True, execution_error="Process timed out after 45 seconds"
        )

        result = run_deptry_check_impl(
            PYTHON, str(tmp_path), ["src"], timeout_seconds=45
        )

        assert result.return_code == -1
        assert result.messages == []
        assert result.error == "timed out after 45 seconds"

    @patch(f"{MODULE_PATH}.execute_command")
    def test_execution_error(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.return_value = make_command_result(
            return_code=-1,
            execution_error="FileNotFoundError: python not found",
            stderr="details",
        )

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.messages == []
        assert result.error is not None
        assert "python not found" in result.error
        assert "details" in result.error

    @patch(f"{MODULE_PATH}.execute_command")
    def test_tool_missing(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.return_value = make_command_result(
            return_code=1, stderr=f"{PYTHON}: No module named deptry"
        )

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.messages == []
        assert result.error == (
            f"deptry is not installed in the Python environment at {PYTHON}."
        )

    @pytest.mark.parametrize(
        "flag", [["--json-output", "x.json"], ["--json-output=x.json"], ["-o", "x"]]
    )
    @patch(f"{MODULE_PATH}.execute_command")
    def test_output_flags_rejected(
        self, mock_exec: Any, flag: list[str], tmp_path: Path
    ) -> None:
        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"], extra_args=flag)

        mock_exec.assert_not_called()
        assert result.return_code == -1
        assert result.messages == []
        assert result.error == (
            f"{flag[0]} changes where deptry writes its report and is not "
            "supported; run_deptry_check reads the JSON report itself."
        )

    @patch(f"{MODULE_PATH}.execute_command")
    def test_temp_dir_removed(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.side_effect = _writing_side_effect("[]", return_code=0)

        run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        out = _output_path(mock_exec.call_args.args[0])
        assert not os.path.exists(os.path.dirname(out))

    @patch(f"{MODULE_PATH}.execute_command")
    def test_temp_dir_removed_on_error(self, mock_exec: Any, tmp_path: Path) -> None:
        mock_exec.side_effect = _writing_side_effect("{oops", return_code=1)

        result = run_deptry_check_impl(PYTHON, str(tmp_path), ["src"])

        assert result.error is not None
        out = _output_path(mock_exec.call_args.args[0])
        assert not os.path.exists(os.path.dirname(out))

    def test_missing_project_dir(self) -> None:
        with pytest.raises(FileNotFoundError, match="not-a-real-dir"):
            run_deptry_check_impl(PYTHON, "/not-a-real-dir", ["src"])
