"""Tests for code_checker_ruff.runners module."""

import json
from typing import Any
from unittest.mock import patch

from mcp_tools_py.code_checker_ruff.runners import (
    _build_ruff_command,
    run_ruff_check_impl,
    run_ruff_fix_impl,
)
from tests.conftest import make_command_result

MODULE_PATH = "mcp_tools_py.code_checker_ruff.runners"


def _make_ruff_json(violations: list[dict[str, Any]]) -> str:
    """Build ruff JSON output from simplified violation dicts."""
    items = []
    for v in violations:
        items.append(
            {
                "code": v.get("code", "E501"),
                "message": v.get("message", "Line too long"),
                "filename": v.get("filename", "/project/src/foo.py"),
                "url": v.get("url", "https://docs.astral.sh/ruff/rules/E501"),
                "fix": v.get("fix"),
                "noqa_row": v.get("noqa_row", 10),
                "location": {"row": v.get("line", 10), "column": v.get("col", 1)},
                "end_location": {
                    "row": v.get("end_line", 10),
                    "column": v.get("end_col", 80),
                },
            }
        )
    return json.dumps(items)


class TestBuildRuffCommand:
    """Tests for _build_ruff_command."""

    def test_basic(self) -> None:
        cmd = _build_ruff_command("/usr/bin/ruff", ["src"])
        assert cmd == [
            "/usr/bin/ruff",
            "check",
            "--output-format",
            "json",
            "src",
        ]

    def test_with_select(self) -> None:
        cmd = _build_ruff_command("/usr/bin/ruff", ["src"], select=["D", "DOC"])
        assert "--select" in cmd
        idx = cmd.index("--select")
        assert cmd[idx + 1] == "D,DOC"

    def test_with_extra_args(self) -> None:
        cmd = _build_ruff_command(
            "/usr/bin/ruff",
            ["src"],
            extra_args=["--preview"],
        )
        assert "--preview" in cmd

    def test_with_fix(self) -> None:
        cmd = _build_ruff_command("/usr/bin/ruff", ["src"], fix=True)
        assert cmd[1] == "check"
        assert "--fix" in cmd

    def test_multiple_directories(self) -> None:
        cmd = _build_ruff_command("/usr/bin/ruff", ["src", "tests"])
        assert cmd[-2:] == ["src", "tests"]


class TestRunRuffCheckImpl:
    """Tests for run_ruff_check_impl."""

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_no_violations(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(return_code=0, stdout="[]")

        result = run_ruff_check_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert result == "No ruff issues found."

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_with_violations(self, mock_exec: Any, _mock_isdir: Any) -> None:
        output = _make_ruff_json(
            [
                {
                    "code": "E501",
                    "message": "Line too long",
                    "filename": "/project/src/a.py",
                },
            ]
        )
        mock_exec.return_value = make_command_result(return_code=1, stdout=output)

        result = run_ruff_check_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert "E501" in result
        assert "Line too long" in result

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_error_exit_code_2(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(
            return_code=2,
            stderr="error: invalid config",
        )

        result = run_ruff_check_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert "Ruff error" in result
        assert "invalid config" in result

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_execution_error(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(
            execution_error="FileNotFoundError: ruff not found",
        )

        result = run_ruff_check_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert "execution error" in result.lower()

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_timeout(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(timed_out=True)

        result = run_ruff_check_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert "timed out" in result.lower()

    def test_invalid_project_dir(self) -> None:
        """Raise FileNotFoundError when project_dir does not exist."""
        import pytest

        with pytest.raises(FileNotFoundError, match="not-a-real-dir"):
            run_ruff_check_impl("/usr/bin/ruff", "/not-a-real-dir", ["src"])


class TestRunRuffFixImpl:
    """Tests for run_ruff_fix_impl."""

    def test_invalid_project_dir(self) -> None:
        """Raise FileNotFoundError when project_dir does not exist."""
        import pytest

        with pytest.raises(FileNotFoundError, match="not-a-real-dir"):
            run_ruff_fix_impl("/usr/bin/ruff", "/not-a-real-dir", ["src"])

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_applies_fixes(self, mock_exec: Any, _mock_isdir: Any) -> None:
        pre_check_output = _make_ruff_json(
            [
                {
                    "code": "F401",
                    "message": "Unused import",
                    "filename": "/project/src/a.py",
                    "fix": {"applicability": "safe", "edits": []},
                },
                {
                    "code": "F401",
                    "message": "Unused import",
                    "filename": "/project/src/b.py",
                    "fix": {"applicability": "safe", "edits": []},
                },
            ]
        )
        post_fix_output = "[]"  # All fixed

        mock_exec.side_effect = [
            make_command_result(return_code=1, stdout=pre_check_output),
            make_command_result(return_code=0, stdout=post_fix_output),
        ]

        result = run_ruff_fix_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert "2 files" in result
        assert mock_exec.call_count == 2
        # Second call should have --fix
        fix_cmd = mock_exec.call_args_list[1][0][0]
        assert "--fix" in fix_cmd

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_no_fixable_violations(self, mock_exec: Any, _mock_isdir: Any) -> None:
        output = _make_ruff_json(
            [
                {"code": "E501", "message": "Line too long", "fix": None},
            ]
        )
        mock_exec.return_value = make_command_result(return_code=1, stdout=output)

        result = run_ruff_fix_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert "no fixable" in result.lower() or "no files modified" in result.lower()
        # Should only call once (pre-check only, no fix needed)
        mock_exec.assert_called_once()

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_execution_error(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(
            execution_error="FileNotFoundError: ruff not found",
        )

        result = run_ruff_fix_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert "execution error" in result.lower()

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_timeout(self, mock_exec: Any, _mock_isdir: Any) -> None:
        mock_exec.return_value = make_command_result(timed_out=True)

        result = run_ruff_fix_impl(
            "/usr/bin/ruff",
            "/project",
            ["src"],
        )

        assert "timed out" in result.lower()

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_pre_check_exit_code_2(self, mock_exec: Any, _mock_isdir: Any) -> None:
        """Return error when pre-check exits with code 2."""
        mock_exec.return_value = make_command_result(
            return_code=2, stderr="error: invalid config"
        )

        result = run_ruff_fix_impl("/usr/bin/ruff", "/project", ["src"])

        assert "Ruff error" in result
        assert "invalid config" in result
        mock_exec.assert_called_once()

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_pre_check_parse_error(self, mock_exec: Any, _mock_isdir: Any) -> None:
        """Propagate parse error from pre-check output."""
        mock_exec.return_value = make_command_result(
            return_code=1, stdout="not valid json"
        )

        result = run_ruff_fix_impl("/usr/bin/ruff", "/project", ["src"])

        assert "parse" in result.lower() or "json" in result.lower()
        mock_exec.assert_called_once()

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_fix_exit_code_2(self, mock_exec: Any, _mock_isdir: Any) -> None:
        """Return error when fix step exits with code 2."""
        pre_check_output = _make_ruff_json(
            [
                {
                    "code": "F401",
                    "message": "Unused import",
                    "filename": "/project/src/a.py",
                    "fix": {"applicability": "safe", "edits": []},
                },
            ]
        )
        mock_exec.side_effect = [
            make_command_result(return_code=1, stdout=pre_check_output),
            make_command_result(return_code=2, stderr="error: fix failed"),
        ]

        result = run_ruff_fix_impl("/usr/bin/ruff", "/project", ["src"])

        assert "Ruff fix error" in result
        assert "fix failed" in result
        assert mock_exec.call_count == 2

    @patch("os.path.isdir", return_value=True)
    @patch(f"{MODULE_PATH}.execute_command")
    def test_post_fix_parse_error(self, mock_exec: Any, _mock_isdir: Any) -> None:
        """Return error when post-fix output cannot be parsed."""
        pre_check_output = _make_ruff_json(
            [
                {
                    "code": "F401",
                    "message": "Unused import",
                    "filename": "/project/src/a.py",
                    "fix": {"applicability": "safe", "edits": []},
                },
            ]
        )
        mock_exec.side_effect = [
            make_command_result(return_code=1, stdout=pre_check_output),
            make_command_result(return_code=1, stdout="not valid json"),
        ]

        result = run_ruff_fix_impl("/usr/bin/ruff", "/project", ["src"])

        assert "applied fixes but could not parse" in result.lower()
        assert mock_exec.call_count == 2
