"""Test mypy runner functionality."""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_mypy import run_mypy_check
from mcp_tools_py.code_checker_mypy.models import MypyResult
from mcp_tools_py.code_checker_mypy.parsers import parse_mypy_json_output
from mcp_tools_py.code_checker_mypy.runners import _describe_cache, _resolve_cache_dir
from tests.conftest import make_command_result

_JSON_ERROR = '{"file": "a.py", "line": 1, "severity": "error", "message": "Bad"}'
_JSON_NOTE = '{"file": "a.py", "line": 1, "severity": "note", "message": "Seen"}'
_WARNING = "Warning: unused section in mypy.ini"
_INTERNAL_ERROR = "INTERNAL ERROR -- Please try using mypy master on GitHub"
# Longer than the 500 characters truncate_stderr keeps, with a unique last line
_LONG_TRACEBACK = (
    "Traceback (most recent call last):\n" + "x" * 600 + "\nthe real cause"
)


def test_run_mypy_check_on_project() -> None:
    """Test running mypy on the actual project."""
    result = run_mypy_check(
        project_dir=".",
        python_executable=sys.executable,
        target_directories=["src"],
    )

    # 0=no errors, 1=errors found, 2=blocking or internal error
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

    @pytest.mark.parametrize(
        "flag",
        ["--no-color-output", "--show-column-numbers", "--show-error-codes"],
    )
    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_default_call_sends_output_flag(
        self, mock_exec: Any, tmp_path: Path, flag: str
    ) -> None:
        command, _ = self._run(mock_exec, tmp_path)
        assert flag in command

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_default_call_sends_json_output(
        self, mock_exec: Any, tmp_path: Path
    ) -> None:
        command, _ = self._run(mock_exec, tmp_path)

        index = command.index("--output")
        assert command[index + 1] == "json"

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_cache_dir_sent_when_requested(
        self, mock_exec: Any, tmp_path: Path
    ) -> None:
        command, _ = self._run(mock_exec, tmp_path, cache_dir="cache")

        index = command.index("--cache-dir")
        assert command[index + 1] == "cache"

    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_cache_dir_omitted_by_default(self, mock_exec: Any, tmp_path: Path) -> None:
        command, _ = self._run(mock_exec, tmp_path)
        assert "--cache-dir" not in command

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

    @pytest.fixture(autouse=True)
    def _no_ambient_cache_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An ambient MYPY_CACHE_DIR would override the config these tests set."""
        monkeypatch.delenv("MYPY_CACHE_DIR", raising=False)

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
        assert "could not be resolved" in error

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

    def test_resolve_cache_dir_defaults_to_mypy_cache_uncertainly(
        self, tmp_path: Path
    ) -> None:
        """With no local config, the default path is an assumption, not a fact."""
        assert _resolve_cache_dir(str(tmp_path), None) == (
            os.path.join(str(tmp_path), ".mypy_cache"),
            False,
        )

    def test_resolve_cache_dir_reads_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mypy]\ncache_dir = "x"\n', encoding="utf-8"
        )

        assert _resolve_cache_dir(str(tmp_path), None) == (
            os.path.join(str(tmp_path), "x"),
            True,
        )

    def test_resolve_cache_dir_gives_up_on_ini_config(self, tmp_path: Path) -> None:
        (tmp_path / "mypy.ini").write_text("[mypy]\n", encoding="utf-8")

        assert _resolve_cache_dir(str(tmp_path), None) == (None, False)

    def test_resolve_cache_dir_explicit_argument_wins(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mypy]\ncache_dir = "x"\n', encoding="utf-8"
        )

        assert _resolve_cache_dir(str(tmp_path), "chosen") == (
            os.path.join(str(tmp_path), "chosen"),
            True,
        )

    def test_resolve_cache_dir_env_beats_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MYPY_CACHE_DIR overrides the config file, so it wins here too."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mypy]\ncache_dir = "x"\n', encoding="utf-8"
        )
        monkeypatch.setenv("MYPY_CACHE_DIR", "from_env")

        assert _resolve_cache_dir(str(tmp_path), None) == (
            os.path.join(str(tmp_path), "from_env"),
            True,
        )

    def test_resolve_cache_dir_argument_beats_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--cache-dir is parsed after the environment override, so it wins."""
        monkeypatch.setenv("MYPY_CACHE_DIR", "from_env")

        assert _resolve_cache_dir(str(tmp_path), "chosen") == (
            os.path.join(str(tmp_path), "chosen"),
            True,
        )

    def test_resolve_cache_dir_expands_home_in_config(self, tmp_path: Path) -> None:
        """Mypy expands ~ in a config cache_dir, so it is not a project subpath."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mypy]\ncache_dir = "~/.cache/mypy"\n', encoding="utf-8"
        )

        assert _resolve_cache_dir(str(tmp_path), None) == (
            os.path.expanduser("~/.cache/mypy"),
            True,
        )

    def test_resolve_cache_dir_expands_vars_in_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CACHE_ROOT", "rooted")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mypy]\ncache_dir = "$CACHE_ROOT/c"\n', encoding="utf-8"
        )

        assert _resolve_cache_dir(str(tmp_path), None) == (
            os.path.join(str(tmp_path), "rooted/c"),
            True,
        )

    def test_resolve_cache_dir_expands_home_but_not_vars_in_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mypy runs expanduser over MYPY_CACHE_DIR, but not expandvars."""
        monkeypatch.setenv("CACHE_ROOT", "rooted")
        monkeypatch.setenv("MYPY_CACHE_DIR", "$CACHE_ROOT/c")

        assert _resolve_cache_dir(str(tmp_path), None) == (
            os.path.join(str(tmp_path), "$CACHE_ROOT/c"),
            True,
        )

        monkeypatch.setenv("MYPY_CACHE_DIR", "~/env_cache")

        assert _resolve_cache_dir(str(tmp_path), None) == (
            os.path.expanduser("~/env_cache"),
            True,
        )


class TestMypyExitReporting:
    """Every failed exit is reported, and stderr stays reachable on its own."""

    @staticmethod
    def _run(mock_exec: Any, tmp_path: Path, **kwargs: Any) -> MypyResult:
        """Run the checker against a mocked mypy process."""
        mock_exec.return_value = make_command_result(**kwargs)
        return run_mypy_check(
            project_dir=str(tmp_path),
            python_executable=sys.executable,
            target_directories=["."],
        )

    @pytest.mark.parametrize(
        "return_code, stdout, stderr, expected_error, expected_messages, expected_stderr",
        [
            pytest.param(0, "", _WARNING, None, 0, _WARNING, id="rc0-warning"),
            pytest.param(0, "", "", None, 0, None, id="rc0-silent"),
            pytest.param(
                1,
                "",
                _LONG_TRACEBACK,
                f"mypy exited with code 1: {_LONG_TRACEBACK}",
                0,
                None,
                id="rc1-traceback-kept-whole",
            ),
            pytest.param(
                1, _JSON_ERROR, _WARNING, None, 1, _WARNING, id="rc1-error-and-warning"
            ),
            pytest.param(1, _JSON_NOTE, "", None, 1, None, id="rc1-note-only"),
            pytest.param(
                2,
                "",
                "Cannot decode file",
                "mypy exited with code 2: Cannot decode file",
                0,
                None,
                id="rc2-stderr-text",
            ),
            pytest.param(
                2,
                "not json",
                "",
                "mypy exited with code 2: not json",
                0,
                None,
                id="rc2-stdout-text",
            ),
            pytest.param(
                2,
                "",
                f"{_WARNING}\n{_JSON_ERROR}",
                None,
                1,
                _WARNING,
                id="rc2-messages-on-stderr",
            ),
            pytest.param(
                2,
                _JSON_ERROR,
                _INTERNAL_ERROR,
                None,
                1,
                _INTERNAL_ERROR,
                id="rc2-error-and-internal-error",
            ),
            pytest.param(
                2,
                _JSON_NOTE,
                _INTERNAL_ERROR,
                f"mypy exited with code 2: {_JSON_NOTE}\n{_INTERNAL_ERROR}",
                0,
                None,
                id="rc2-note-and-internal-error",
            ),
            pytest.param(
                2,
                "",
                "",
                "mypy exited with code 2: no output",
                0,
                None,
                id="rc2-silent",
            ),
            pytest.param(
                3,
                "",
                "",
                "mypy exited with code 3: no output",
                0,
                None,
                id="rc3-silent",
            ),
            pytest.param(
                -11,
                _JSON_NOTE,
                "",
                f"mypy exited with code -11: {_JSON_NOTE}",
                0,
                None,
                id="signal-note-only",
            ),
            pytest.param(
                1, "null", "", "mypy exited with code 1: null", 0, None, id="rc1-null"
            ),
            pytest.param(
                0,
                "null",
                "",
                parse_mypy_json_output("null")[1],
                0,
                None,
                id="rc0-null-parse-error",
            ),
        ],
    )
    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_exit_is_reported(
        self,
        mock_exec: Any,
        tmp_path: Path,
        return_code: int,
        stdout: str,
        stderr: str,
        expected_error: str | None,
        expected_messages: int,
        expected_stderr: str | None,
    ) -> None:
        result = self._run(
            mock_exec, tmp_path, return_code=return_code, stdout=stdout, stderr=stderr
        )

        assert result.return_code == return_code
        assert result.error == expected_error
        assert len(result.messages) == expected_messages
        assert result.stderr == expected_stderr

    @pytest.mark.parametrize(
        "return_code, stdout",
        [(1, _JSON_ERROR), (2, _JSON_NOTE)],
        ids=["reported-findings", "failed-exit"],
    )
    @patch("mcp_tools_py.code_checker_mypy.runners.execute_command")
    def test_raw_output_holds_stdout_and_stderr(
        self, mock_exec: Any, tmp_path: Path, return_code: int, stdout: str
    ) -> None:
        result = self._run(
            mock_exec, tmp_path, return_code=return_code, stdout=stdout, stderr=_WARNING
        )

        assert result.raw_output == f"{stdout}\n{_WARNING}"
