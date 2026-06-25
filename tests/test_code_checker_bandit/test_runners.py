"""Tests for code_checker_bandit.runners module."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_bandit.runners import (
    _build_bandit_command,
    run_bandit_check_impl,
)
from tests.conftest import make_command_result

MODULE_PATH = "mcp_tools_py.code_checker_bandit.runners"


def _make_bandit_json(
    results: list[dict[str, Any]] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> str:
    """Build bandit JSON output from simplified dicts."""
    data: dict[str, Any] = {
        "results": [],
        "errors": [],
    }
    for r in results or []:
        data["results"].append(
            {
                "test_id": r.get("test_id", "B101"),
                "test_name": r.get("test_name", "assert_used"),
                "issue_severity": r.get("issue_severity", "LOW"),
                "issue_confidence": r.get("issue_confidence", "HIGH"),
                "issue_text": r.get("issue_text", "Use of assert detected."),
                "filename": r.get("filename", "/project/src/foo.py"),
                "line_number": r.get("line_number", 10),
                "more_info": r.get(
                    "more_info",
                    "https://bandit.readthedocs.io/en/latest/plugins/b101.html",
                ),
                "issue_cwe": r.get(
                    "issue_cwe", {"id": 703, "link": "https://cwe.mitre.org/703"}
                ),
            }
        )
    for e in errors or []:
        data["errors"].append(e)
    return json.dumps(data)


class TestBuildBanditCommand:
    """Tests for _build_bandit_command."""

    def test_build_command_basic(self) -> None:
        cmd = _build_bandit_command("/usr/bin/bandit", ["src"], "/tmp/out.json")
        assert cmd == [
            "/usr/bin/bandit",
            "-f",
            "json",
            "-o",
            "/tmp/out.json",
            "-r",
            "src",
        ]

    def test_build_command_with_extra_args(self) -> None:
        cmd = _build_bandit_command(
            "/usr/bin/bandit",
            ["src"],
            "/tmp/out.json",
            extra_args=["--severity-level", "high"],
        )
        assert cmd == [
            "/usr/bin/bandit",
            "-f",
            "json",
            "-o",
            "/tmp/out.json",
            "-r",
            "src",
            "--severity-level",
            "high",
        ]

    def test_build_command_multiple_directories(self) -> None:
        cmd = _build_bandit_command("/usr/bin/bandit", ["src", "lib"], "/tmp/out.json")
        assert cmd == [
            "/usr/bin/bandit",
            "-f",
            "json",
            "-o",
            "/tmp/out.json",
            "-r",
            "src",
            "lib",
        ]


def _writing_side_effect(output: str, return_code: int) -> Any:
    """Build an execute_command side_effect that writes ``output`` to the -o path."""

    def _write(cmd: list[str], cwd: str | None = None) -> Any:
        out = cmd[cmd.index("-o") + 1]
        Path(out).write_text(output, encoding="utf-8")
        return make_command_result(return_code=return_code)

    return _write


class TestRunBanditCheckImpl:
    """Tests for run_bandit_check_impl."""

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_no_issues(self, mock_exec: Any, _mock_isdir: Any) -> None:
        output = _make_bandit_json()
        mock_exec.side_effect = _writing_side_effect(output, return_code=0)

        result = run_bandit_check_impl("/usr/bin/bandit", "/project", ["src"])

        assert result.return_code == 0
        assert result.messages == []
        assert result.errors == []
        assert result.error is None

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_with_issues(self, mock_exec: Any, _mock_isdir: Any) -> None:
        output = _make_bandit_json(
            results=[
                {
                    "test_id": "B101",
                    "test_name": "assert_used",
                    "issue_text": "Use of assert detected.",
                    "filename": "/project/src/foo.py",
                    "line_number": 42,
                },
            ]
        )
        mock_exec.side_effect = _writing_side_effect(output, return_code=1)

        result = run_bandit_check_impl("/usr/bin/bandit", "/project", ["src"])

        assert result.return_code == 1
        assert len(result.messages) == 1
        assert result.messages[0].test_id == "B101"
        assert result.messages[0].line_number == 42
        assert result.error is None

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_empty_output_file_is_error(self, mock_exec: Any, _mock_isdir: Any) -> None:
        # Successful return code but no JSON file written: an anomaly, not
        # "no issues". The guard must convert this silent failure into a loud,
        # legible error.
        mock_exec.return_value = make_command_result(return_code=0)

        result = run_bandit_check_impl("/usr/bin/bandit", "/project", ["src"])

        assert result.messages == []
        assert result.error is not None
        assert "output file" in result.error

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_error_exit_code_gt_1(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=2, stderr="bandit: error: invalid config"
        )

        result = run_bandit_check_impl("/usr/bin/bandit", "/project", ["src"])

        assert result.return_code == 2
        assert result.messages == []
        assert result.error is not None
        assert "invalid config" in result.error

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_execution_error(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(
            execution_error="FileNotFoundError: bandit not found"
        )

        result = run_bandit_check_impl("/usr/bin/bandit", "/project", ["src"])

        assert result.return_code == -1
        assert result.messages == []
        assert result.error is not None
        assert "bandit not found" in result.error

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_timeout(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(timed_out=True)

        result = run_bandit_check_impl("/usr/bin/bandit", "/project", ["src"])

        assert result.return_code == -1
        assert result.messages == []
        assert result.error == "timed out"

    def test_invalid_project_dir(self) -> None:
        with pytest.raises(FileNotFoundError, match="not-a-real-dir"):
            run_bandit_check_impl("/usr/bin/bandit", "/not-a-real-dir", ["src"])
