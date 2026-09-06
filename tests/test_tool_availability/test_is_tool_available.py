"""Tests for the lazy _is_tool_available lookup."""

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_command_result
from tests.test_tool_availability._helpers import _create_server, _dummy_python


class TestIsToolAvailable:
    """Test _is_tool_available lazy caching."""

    def test_first_call_runs_subprocess_and_caches(self, tmp_path: Path) -> None:
        """First call to _is_tool_available runs subprocess and caches result."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(
                return_code=0, stdout="pytest 8.0.0"
            )

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
            mock_exec.reset_mock()
            mock_exec.return_value = make_command_result(
                return_code=0, stdout="pytest 8.0.0"
            )

            result = server._is_tool_available("pytest")

            assert result is True
            assert server._tool_availability["pytest"] is True
            mock_exec.assert_called_once()

    def test_script_on_disk_skips_subprocess(self, tmp_path: Path) -> None:
        """A console script next to the interpreter means available, no probe."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path, "pytest"),
            )
            mock_exec.reset_mock()

            assert server._is_tool_available("pytest") is True
            mock_exec.assert_not_called()

    def test_script_group_fast_path_records_binary(self, tmp_path: Path) -> None:
        """A script-group tool found by the fast path records its path."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            python = _dummy_python(tmp_path, "ruff")
            server = _create_server(
                project_dir=Path("/project"), python_executable=python
            )
            del server._tool_availability["ruff"]
            del server._tool_binaries["ruff"]
            mock_exec.reset_mock()

            assert server._is_tool_available("ruff") is True
            assert server._tool_binaries["ruff"] == os.path.join(
                os.path.dirname(python), "ruff.exe" if os.name == "nt" else "ruff"
            )
            mock_exec.assert_not_called()

    def test_script_only_tool_never_probes(self, tmp_path: Path) -> None:
        """A tool with no module and no console script is unavailable, no probe."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
            del server._tool_availability["lint-imports"]
            mock_exec.reset_mock()

            assert server._is_tool_available("lint-imports") is False
            assert server._tool_availability["lint-imports"] is False
            mock_exec.assert_not_called()

    def test_timeout_fails_open_and_caches(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A probe that times out is assumed available, cached, and warned about."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
            mock_exec.reset_mock()
            mock_exec.return_value = make_command_result(
                return_code=-1,
                timed_out=True,
                execution_error="Process timed out after 30 seconds",
            )

            with caplog.at_level(logging.WARNING, logger="mcp_tools_py.server"):
                result = server._is_tool_available("pytest")

            assert result is True
            assert server._tool_availability["pytest"] is True
            assert any(
                record.levelno == logging.WARNING and "pytest" in record.getMessage()
                for record in caplog.records
            )

            assert server._is_tool_available("pytest") is True
            mock_exec.assert_called_once()

    def test_execution_error_without_timeout_caches_false(self, tmp_path: Path) -> None:
        """A non-timeout execution error still marks the tool unavailable."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
            mock_exec.reset_mock()
            mock_exec.return_value = make_command_result(
                return_code=-1,
                timed_out=False,
                execution_error="spawn failed",
            )

            result = server._is_tool_available("pytest")

            assert result is False
            assert server._tool_availability["pytest"] is False

    def test_probe_disables_plugin_autoload(self, tmp_path: Path) -> None:
        """The probe runs with plugin autoload disabled and a 30s timeout."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
            mock_exec.reset_mock()
            mock_exec.return_value = make_command_result(
                return_code=0, stdout="pytest 8.0.0"
            )

            server._is_tool_available("pytest")

            kwargs = mock_exec.call_args.kwargs
            assert kwargs["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
            assert kwargs["timeout_seconds"] == 30

    def test_second_call_returns_cached_no_subprocess(self) -> None:
        """Second call returns cached result without running subprocess."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability["pytest"] = True
            mock_exec.reset_mock()

            result = server._is_tool_available("pytest")

            assert result is True
            mock_exec.assert_not_called()

    def test_eager_tool_returned_from_cache(self) -> None:
        """Eager tools populated at init are returned from cache without subprocess."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(
                "mcp_tools_py.utils.python_environment.os.path.exists",
                return_value=True,
            ),
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"), venv_path="/mock/venv"
            )
            mock_exec.reset_mock()

            result = server._is_tool_available("ruff")

            assert result is True
            mock_exec.assert_not_called()

    def test_subprocess_failure_marks_unavailable(self, tmp_path: Path) -> None:
        """When subprocess fails, result is False and cached."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
            mock_exec.reset_mock()
            mock_exec.return_value = make_command_result(
                return_code=1,
                stderr="No module named pytest",
                execution_error="error",
            )

            result = server._is_tool_available("pytest")

            assert result is False
            assert server._tool_availability["pytest"] is False

    def test_subprocess_success_marks_available(self, tmp_path: Path) -> None:
        """When subprocess succeeds, result is True and cached."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
            mock_exec.reset_mock()
            mock_exec.return_value = make_command_result(
                return_code=0, stdout="pytest 8.0.0"
            )

            result = server._is_tool_available("pytest")

            assert result is True
            assert server._tool_availability["pytest"] is True
