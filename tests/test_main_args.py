"""Tests for command line argument handling in main.py."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_tools_py.main import _build_parser, main, parse_args


def _run_main(project_dir: Path, *extra_args: str) -> None:
    """Run main() with mocked logging setup and server creation."""
    argv = ["mcp-tools-py", "--project-dir", str(project_dir), "--console-only"]
    argv.extend(extra_args)
    with (
        patch("sys.argv", argv),
        patch("mcp_tools_py.main.setup_logging"),
        patch("mcp_tools_py.main.create_server"),
    ):
        main()


class TestVenvPathDeprecation:
    """Test the soft deprecation of --venv-path."""

    def test_venv_path_hidden_from_help(self) -> None:
        assert "--venv-path" not in _build_parser().format_help()

    def test_venv_path_still_accepted(self) -> None:
        with patch(
            "sys.argv",
            ["mcp-tools-py", "--project-dir", "X", "--venv-path", "Y"],
        ):
            args = parse_args()
        assert args.venv_path == "Y"

    def test_venv_path_logs_deprecation_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="mcp_tools_py.main"):
            _run_main(tmp_path, "--venv-path", str(tmp_path))

        warnings = [
            record.getMessage()
            for record in caplog.records
            if record.levelno == logging.WARNING
        ]
        assert any("deprecated" in message for message in warnings)

    def test_no_warning_without_venv_path(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="mcp_tools_py.main"):
            _run_main(tmp_path)

        assert not [
            record
            for record in caplog.records
            if "deprecated" in record.getMessage().lower()
        ]

    def test_epilog_does_not_advertise_venv_path(self) -> None:
        epilog = _build_parser().epilog
        assert epilog is not None
        assert "--python-executable" in epilog
        assert "--venv-path" not in epilog


class TestMissingInterpreter:
    """Test the startup failure for an unresolvable --python-executable."""

    def test_missing_interpreter_exits_with_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        argv = [
            "mcp-tools-py",
            "--project-dir",
            str(tmp_path),
            "--console-only",
            "--python-executable",
            str(tmp_path / "missing" / "python"),
        ]
        with (
            patch("sys.argv", argv),
            patch("mcp_tools_py.main.setup_logging"),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        # stdout is the stdio protocol channel, so the message goes to stderr.
        assert "Error: Python interpreter not found" in captured.err
