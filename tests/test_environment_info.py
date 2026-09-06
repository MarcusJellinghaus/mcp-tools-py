"""Tests for the one-shot environment probe and its parsed result."""

import json
import platform
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_tools_py.utils.environment_info import (
    PROBED_MODULES,
    get_environment_info,
    probe_script_path,
)
from mcp_tools_py.utils.subprocess_runner import execute_command
from tests.conftest import make_command_result
from tests.test_tool_availability._helpers import _create_server, _dummy_python

_BLOB = json.dumps(
    {
        "version": "3.11.9",
        "sys_path": ["/first", "/second"],
        "distributions": {"pylint": "3.2.0"},
        "importable": {"pylint": True, "pytest": True, "mypy": False},
    }
)


class TestGetEnvironmentInfo:
    """Test parsing, caching and the fail-open failure shape."""

    def test_parses_well_formed_blob(self) -> None:
        """A well-formed probe blob becomes an EnvironmentInfo."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout=_BLOB)

            info = get_environment_info("/some/python")

            assert info.version == "3.11.9"
            assert info.sys_path == ("/first", "/second")
            assert info.distributions == {"pylint": "3.2.0"}
            assert info.importable["pytest"] is True
            assert info.importable["mypy"] is False
            assert info.error is None

    def test_success_is_cached(self) -> None:
        """A successful probe runs once per interpreter path."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout=_BLOB)

            first = get_environment_info("/some/python")
            second = get_environment_info("/some/python")

            assert first is second
            mock_exec.assert_called_once()

    def test_failure_is_cached_and_fails_open(self) -> None:
        """A non-zero exit is remembered, and reports every module available."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=1, stderr="no such file"
            )

            first = get_environment_info("/some/python")
            second = get_environment_info("/some/python")

            mock_exec.assert_called_once()
            assert first.error is not None
            assert second.error is not None
            assert "no such file" in first.error
            assert all(first.importable[name] for name in PROBED_MODULES)

    def test_timeout_fails_open(self) -> None:
        """A probe that times out sets error rather than raising."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=-1,
                timed_out=True,
                execution_error="Process timed out after 30 seconds",
            )

            info = get_environment_info("/some/python")

            assert info.error is not None
            assert "timed out" in info.error
            assert all(info.importable[name] for name in PROBED_MODULES)

    def test_unparsable_stdout_fails_open(self) -> None:
        """Output that is not the expected JSON sets error rather than raising."""
        with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout="not json at all")

            info = get_environment_info("/some/python")

            assert info.error is not None
            assert "unparsable" in info.error
            assert all(info.importable[name] for name in PROBED_MODULES)

    def test_not_probed_until_first_use(self, tmp_path: Path) -> None:
        """Constructing a server runs no probe."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

            mock_exec.assert_not_called()


class TestProbeScript:
    """Test the script itself, run under the current interpreter."""

    def test_probe_script_path_exists(self) -> None:
        """The parent's path arithmetic points at a real file."""
        assert probe_script_path().is_file()

    def test_real_child_reports_importability(self) -> None:
        """The script answers about this interpreter, for real."""
        result = execute_command(
            [
                sys.executable,
                str(probe_script_path()),
                "info",
                "json",
                "pytest",
                "nosuchmodule_xyz",
            ],
            timeout_seconds=60,
        )

        assert result.return_code == 0, result.stderr
        blob = json.loads(result.stdout)
        assert blob["importable"] == {
            "json": True,
            "pytest": True,
            "nosuchmodule_xyz": False,
        }
        assert blob["version"] == platform.python_version()
