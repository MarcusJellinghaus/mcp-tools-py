"""Tests for _resolve_python_executable."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_command_result
from tests.test_tool_availability._helpers import _create_server


class TestResolvePythonExecutable:
    """Test _resolve_python_executable logic."""

    def test_venv_path_windows(self) -> None:
        """When venv_path is set and os.name=='nt', resolve to Scripts/python.exe."""
        project_dir = Path("/project")
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch("mcp_tools_py.server.os.name", "nt"),
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(project_dir=project_dir, venv_path="/my/venv")

            expected = os.path.join("/my/venv", "Scripts", "python.exe")
            assert server._resolved_python == expected

    @pytest.mark.skipif(os.name == "nt", reason="PosixPath unsupported on Windows")
    def test_venv_path_unix(self) -> None:
        """When venv_path is set and os.name!='nt', resolve to bin/python."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch("mcp_tools_py.server.os.name", "posix"),
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(project_dir=Path("/project"), venv_path="/my/venv")

            expected = os.path.join("/my/venv", "bin", "python")
            assert server._resolved_python == expected

    def test_venv_path_not_found_raises(self) -> None:
        """When venv python executable doesn't exist, raise FileNotFoundError."""
        project_dir = Path("/project")
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.os.name", "nt"),
            patch("mcp_tools_py.server.os.path.exists", return_value=False),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            with pytest.raises(FileNotFoundError, match="--venv-path"):
                _create_server(project_dir=project_dir, venv_path="/my/venv")

    def test_python_executable_not_found_raises(self) -> None:
        """When python_executable doesn't exist, raise FileNotFoundError."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            with pytest.raises(FileNotFoundError, match="--python-executable"):
                _create_server(
                    project_dir=Path("/project"),
                    python_executable="/no/such/python3.11",
                )

    def test_bare_name_resolved_on_path(self) -> None:
        """A name without a directory part is looked up on PATH."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch(
                "mcp_tools_py.server.shutil.which", return_value="/usr/bin/python3"
            ) as mock_which,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(
                project_dir=Path("/project"), python_executable="python3"
            )

            assert server._resolved_python == "/usr/bin/python3"
            mock_which.assert_called_once_with("python3")

    def test_python_executable_fallback(self) -> None:
        """When no venv_path but python_executable is set, use it directly."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(
                project_dir=Path("/project"),
                python_executable="/usr/local/bin/python3.11",
            )

            assert server._resolved_python == "/usr/local/bin/python3.11"

    def test_sys_executable_fallback(self) -> None:
        """When neither venv_path nor python_executable is set, use sys.executable."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(project_dir=Path("/project"))

            assert server._resolved_python == sys.executable
