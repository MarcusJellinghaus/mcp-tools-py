"""Tests for the lazy _is_tool_available lookup."""

import json
import logging
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.utils.environment_info import PROBED_MODULES
from tests.conftest import make_command_result
from tests.test_tool_availability._helpers import _create_server, _dummy_python


def _probe_blob(
    importable: Optional[dict[str, bool]] = None,
    distributions: Optional[dict[str, str]] = None,
) -> str:
    """Build the JSON a successful probe writes, with every module importable."""
    reported = {name: True for name in PROBED_MODULES}
    reported.update(importable or {})
    return json.dumps(
        {
            "version": "3.11.9",
            "sys_path": [],
            "distributions": distributions or {},
            "importable": reported,
        }
    )


class TestIsToolAvailable:
    """Test _is_tool_available lazy caching."""

    def test_first_call_probes_and_caches(self, tmp_path: Path) -> None:
        """First call to _is_tool_available probes the environment and caches."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(stdout=_probe_blob())

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
            mock_exec.reset_mock()

            result = server._is_tool_available("pytest")

            assert result is True
            assert server._tool_availability["pytest"] is True
            mock_exec.assert_called_once()

    def test_script_only_tool_never_probes(self, tmp_path: Path) -> None:
        """A tool with no module and no console script is unavailable, no probe."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
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
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
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

    def test_not_importable_marks_unavailable(self, tmp_path: Path) -> None:
        """A successful probe reporting the module missing means unavailable."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(
                stdout=_probe_blob(importable={"pytest": False})
            )

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

            result = server._is_tool_available("pytest")

            assert result is False
            assert server._tool_availability["pytest"] is False

    def test_not_importable_warning_names_installed_distribution(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A missing module whose distribution is installed reads as broken."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(
                stdout=_probe_blob(
                    importable={"pytest": False}, distributions={"pytest": "8.0.0"}
                )
            )

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

            with caplog.at_level(logging.WARNING, logger="mcp_tools_py.server"):
                assert server._is_tool_available("pytest") is False

            messages = [record.getMessage() for record in caplog.records]
            assert any(
                "not importable" in message and "pytest 8.0.0" in message
                for message in messages
            )

    def test_second_call_returns_cached_no_subprocess(self) -> None:
        """Second call returns cached result without running subprocess."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(stdout=_probe_blob())

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
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"), venv_path="/mock/venv"
            )
            mock_exec.reset_mock()

            result = server._is_tool_available("ruff")

            assert result is True
            mock_exec.assert_not_called()

    def test_probe_success_marks_available(self, tmp_path: Path) -> None:
        """When the probe reports the module importable, the tool is available."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(stdout=_probe_blob())

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

            result = server._is_tool_available("pytest")

            assert result is True
            assert server._tool_availability["pytest"] is True
