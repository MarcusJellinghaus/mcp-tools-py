"""Test mypy runner functionality."""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_mypy import run_mypy_check
from mcp_tools_py.code_checker_mypy.runners import _describe_cache, _resolve_cache_dir
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


class TestMypyTimeoutMessage:
    """A timeout reports cache state, the exact command and how to retry."""

    @staticmethod
    def _timeout_error(tmp_path: Path, mock_exec: Any, **kwargs: Any) -> str:
        """Run the checker against a timing-out mypy, return the error text."""
        mock_exec.return_value = make_command_result(return_code=1, timed_out=True)
        result = run_mypy_check(
            project_dir=str(tmp_path),
            python_executable=sys.executable,
            target_directories=["."],
            timeout_seconds=7,
            **kwargs,
        )
        assert result.error is not None
        return result.error

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_timeout_message_is_actionable(
        self, mock_exec: Any, tmp_path: Path
    ) -> None:
        error = self._timeout_error(tmp_path, mock_exec)

        assert "7 seconds" in error
        assert os.path.join(str(tmp_path), ".mypy_cache") in error
        assert str(tmp_path) in error
        assert sys.executable in error
        assert "mypy" in error
        assert "timeout_seconds" in error

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_timeout_message_reports_cache_state(
        self, mock_exec: Any, tmp_path: Path
    ) -> None:
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "data.json").write_text("x" * 30, encoding="utf-8")

        error = self._timeout_error(tmp_path, mock_exec, cache_dir="cache")

        assert str(cache) in error
        assert "30 bytes" in error

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_timeout_message_omits_size_when_cache_unresolved(
        self, mock_exec: Any, tmp_path: Path
    ) -> None:
        (tmp_path / "mypy.ini").write_text("[mypy]\n", encoding="utf-8")

        error = self._timeout_error(tmp_path, mock_exec)

        assert "bytes" not in error
        assert "mypy config" in error

    def test_describe_cache_missing_directory(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "nope")

        description = _describe_cache(missing)

        assert missing in description
        assert "does not exist" in description

    def test_describe_cache_reports_size_and_mtime(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "data.json"
        cache_file.write_text("y" * 12, encoding="utf-8")
        expected_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime).isoformat()

        description = _describe_cache(str(tmp_path))

        assert "12 bytes" in description
        assert "1 files" in description
        assert expected_mtime in description

    def test_resolve_cache_dir_defaults_to_mypy_cache(self, tmp_path: Path) -> None:
        assert _resolve_cache_dir(str(tmp_path), None) == os.path.join(
            str(tmp_path), ".mypy_cache"
        )

    def test_resolve_cache_dir_reads_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mypy]\ncache_dir = "x"\n', encoding="utf-8"
        )

        assert _resolve_cache_dir(str(tmp_path), None) == os.path.join(
            str(tmp_path), "x"
        )

    def test_resolve_cache_dir_gives_up_on_ini_config(self, tmp_path: Path) -> None:
        (tmp_path / "mypy.ini").write_text("[mypy]\n", encoding="utf-8")

        assert _resolve_cache_dir(str(tmp_path), None) is None

    def test_resolve_cache_dir_explicit_argument_wins(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mypy]\ncache_dir = "x"\n', encoding="utf-8"
        )

        assert _resolve_cache_dir(str(tmp_path), "chosen") == os.path.join(
            str(tmp_path), "chosen"
        )
