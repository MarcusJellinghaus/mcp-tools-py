"""Test mypy runner functionality."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_mypy import run_mypy_check
from tests.conftest import make_command_result


def test_run_mypy_check_on_project() -> None:
    """Test running mypy on the actual project."""
    result = run_mypy_check(
        project_dir=".",
        python_executable=sys.executable,
        target_directories=["src"],
    )

    # 0=no errors, 1=errors found, 2=config error (should be fixed now)
    assert result.return_code in [
        0,
        1,
    ], f"Unexpected return code {result.return_code}. Error: {result.error}, Raw output: {result.raw_output}"
    assert isinstance(result.messages, list)


def test_run_mypy_check_non_existent_directory() -> None:
    """Test running mypy on a non-existent directory."""
    with pytest.raises(FileNotFoundError, match="Project directory not found"):
        run_mypy_check(
            project_dir="/non/existent/directory", python_executable=sys.executable
        )


def test_run_mypy_check_with_disabled_codes() -> None:
    """Test running mypy with disabled error codes."""
    result = run_mypy_check(
        project_dir=".",
        python_executable=sys.executable,
        disable_error_codes=["import", "arg-type"],
        target_directories=["src"],
    )

    assert result.return_code in [
        0,
        1,
    ], f"Unexpected return code {result.return_code}. Error: {result.error}, Raw output: {result.raw_output}"
    # Verify that disabled codes are not in the results
    for msg in result.messages:
        if msg.code:
            assert msg.code not in ["import", "arg-type"]


class TestMypyCommandConstruction:
    """The command carries only output flags unless the caller asks for more."""

    @staticmethod
    def _run(
        mock_exec: Any, tmp_path: Path, **kwargs: Any
    ) -> tuple[list[str], dict[str, str]]:
        """Run the checker against an empty temp project, return command and env."""
        mock_exec.return_value = make_command_result()
        run_mypy_check(
            project_dir=str(tmp_path),
            python_executable=sys.executable,
            target_directories=["."],
            **kwargs,
        )
        call = mock_exec.call_args.kwargs
        return call["command"], call["env"]

    @pytest.mark.parametrize(
        "flag",
        [
            "--strict",
            "--namespace-packages",
            "--explicit-package-bases",
            "--follow-imports",
        ],
    )
    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_default_call_omits_config_owned_flag(
        self, mock_exec: Any, tmp_path: Path, flag: str
    ) -> None:
        command, _ = self._run(mock_exec, tmp_path)
        assert flag not in command

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_default_call_sets_neither_mypy_env_var(
        self, mock_exec: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MYPYPATH", raising=False)
        monkeypatch.delenv("MYPY_NUM_WORKERS", raising=False)

        _, env = self._run(mock_exec, tmp_path)

        assert "MYPYPATH" not in env
        assert "MYPY_NUM_WORKERS" not in env

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_ambient_mypy_num_workers_is_dropped(
        self, mock_exec: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MYPY_NUM_WORKERS", "4")

        _, env = self._run(mock_exec, tmp_path)

        assert "MYPY_NUM_WORKERS" not in env

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_ambient_mypypath_is_passed_through_unchanged(
        self, mock_exec: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MYPYPATH", "/ambient/path")

        _, env = self._run(mock_exec, tmp_path)

        assert env["MYPYPATH"] == "/ambient/path"

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_follow_imports_sent_when_requested(
        self, mock_exec: Any, tmp_path: Path
    ) -> None:
        command, _ = self._run(mock_exec, tmp_path, follow_imports="silent")

        index = command.index("--follow-imports")
        assert command[index + 1] == "silent"

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_disable_error_codes_sent_as_one_pair_each(
        self, mock_exec: Any, tmp_path: Path
    ) -> None:
        command, _ = self._run(
            mock_exec, tmp_path, disable_error_codes=["import", "arg-type"]
        )

        pairs = [
            (command[i], command[i + 1])
            for i, arg in enumerate(command)
            if arg == "--disable-error-code"
        ]
        assert pairs == [
            ("--disable-error-code", "import"),
            ("--disable-error-code", "arg-type"),
        ]
