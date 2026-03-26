"""Tests for startup tool validation: _resolve_python_executable and _check_tool_availability."""

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.utils.subprocess_runner import CommandResult
from tests.conftest import make_command_result


def _create_server(**kwargs: Any) -> Any:
    """Create a CodeCheckerServer with mocked FastMCP and execute_command."""
    from mcp_tools_py.server import CodeCheckerServer

    return CodeCheckerServer(**kwargs)


# ---------------------------------------------------------------------------
# _resolve_python_executable tests
# ---------------------------------------------------------------------------


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

            with pytest.raises(FileNotFoundError):
                _create_server(project_dir=project_dir, venv_path="/my/venv")

    def test_python_executable_fallback(self) -> None:
        """When no venv_path but python_executable is set, use it directly."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
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


# ---------------------------------------------------------------------------
# _check_tool_availability tests
# ---------------------------------------------------------------------------


class TestCheckToolAvailability:
    """Test _check_tool_availability caching."""

    def test_all_tools_available(self) -> None:
        """When all tools return success, all should be True."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(
                return_code=0, stdout="tool 1.0.0"
            )

            server = _create_server(
                project_dir=Path("/project"), venv_path="/mock/venv"
            )

            assert server._tool_availability == {
                "pytest": True,
                "pylint": True,
                "mypy": True,
                "lint-imports": True,
            }

    def test_one_tool_missing(self) -> None:
        """When one tool fails, it should be False while others True."""

        def side_effect(command: list[str], **kwargs: Any) -> CommandResult:
            # pytest missing, others available
            if "pytest" in command:
                return make_command_result(
                    return_code=1,
                    stderr="No module named pytest",
                    execution_error="error",
                )
            return make_command_result(return_code=0, stdout="tool 1.0.0")

        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.side_effect = side_effect

            server = _create_server(project_dir=Path("/project"))

            assert server._tool_availability["pytest"] is False
            assert server._tool_availability["pylint"] is True
            assert server._tool_availability["mypy"] is True

    def test_all_tools_missing(self) -> None:
        """When all tools fail, all should be False."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(
                return_code=1, execution_error="not found"
            )

            server = _create_server(project_dir=Path("/project"))

            assert server._tool_availability == {
                "pytest": False,
                "pylint": False,
                "mypy": False,
                "lint-imports": False,
            }

    def test_timed_out_tool_marked_unavailable(self) -> None:
        """When a tool check times out, it should be marked as unavailable."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(return_code=1, timed_out=True)

            server = _create_server(project_dir=Path("/project"))

            assert server._tool_availability == {
                "pytest": False,
                "pylint": False,
                "mypy": False,
                "lint-imports": False,
            }

    def test_lint_imports_available_when_binary_exists(self) -> None:
        """When venv_path is set and lint-imports binary exists, mark available."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch("mcp_tools_py.server.os.name", "nt"),
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(
                return_code=0, stdout="tool 1.0.0"
            )

            server = _create_server(
                project_dir=Path("/project"), venv_path="/mock/venv"
            )

            assert server._tool_availability["lint-imports"] is True
            assert server._lint_imports_binary == os.path.join(
                "/mock/venv", "Scripts", "lint-imports.exe"
            )

    def test_lint_imports_unavailable_when_no_venv(self) -> None:
        """When no venv_path is configured, lint-imports is unavailable."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(
                return_code=0, stdout="tool 1.0.0"
            )

            server = _create_server(project_dir=Path("/project"))

            assert server._tool_availability["lint-imports"] is False
            assert server._lint_imports_binary is None

    def test_lint_imports_unavailable_when_binary_missing(self) -> None:
        """When venv_path is set but binary doesn't exist, mark unavailable."""

        def exists_side_effect(path: str) -> bool:
            # Python executable exists, but lint-imports does not
            if "python" in path.lower():
                return True
            return False

        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch("mcp_tools_py.server.os.name", "nt"),
            patch(
                "mcp_tools_py.server.os.path.exists",
                side_effect=exists_side_effect,
            ),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            mock_exec.return_value = make_command_result(
                return_code=0, stdout="tool 1.0.0"
            )

            server = _create_server(
                project_dir=Path("/project"), venv_path="/mock/venv"
            )

            assert server._tool_availability["lint-imports"] is False
            assert server._lint_imports_binary is None


# ---------------------------------------------------------------------------
# Tool handler short-circuit tests
# ---------------------------------------------------------------------------


def _capture_tools(mock_fastmcp: MagicMock) -> dict[str, Any]:
    """Set up tool capture on a mocked FastMCP instance.

    Returns a dict that will be populated with {func_name: func} as tools
    are registered during server construction.
    """
    registered_tools: dict[str, Any] = {}

    def capture_tool(func: Any) -> Any:
        registered_tools[func.__name__] = func
        return func

    mock_fastmcp.return_value.tool.return_value = capture_tool
    return registered_tools


class TestToolHandlerShortCircuit:
    """Test that tool handlers return immediate error when tool unavailable."""

    def test_pytest_unavailable_returns_error(self) -> None:
        """When pytest is unavailable, tool handler returns error string."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            registered_tools = _capture_tools(mock_fastmcp)
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": False,
                "pylint": True,
                "mypy": True,
                "lint-imports": False,
            }

            result = registered_tools["run_pytest_check"]()

            assert "pytest is not available" in result
            assert "Restart the server" in result

    def test_pylint_unavailable_returns_error(self) -> None:
        """When pylint is unavailable, tool handler returns error string."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            registered_tools = _capture_tools(mock_fastmcp)
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": True,
                "pylint": False,
                "mypy": True,
                "lint-imports": False,
            }

            result = registered_tools["run_pylint_check"]()

            assert "pylint is not available" in result
            assert "Restart the server" in result

    def test_mypy_unavailable_returns_error(self) -> None:
        """When mypy is unavailable, tool handler returns error string."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            registered_tools = _capture_tools(mock_fastmcp)
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": True,
                "pylint": True,
                "mypy": False,
                "lint-imports": False,
            }

            result = registered_tools["run_mypy_check"]()

            assert "mypy is not available" in result
            assert "Restart the server" in result

    def test_available_tool_runs_normally(self) -> None:
        """When tool is available, normal execution proceeds."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch("mcp_tools_py.checker_tools.check_code_with_pytest") as mock_check,
        ):
            registered_tools = _capture_tools(mock_fastmcp)
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            mock_check.return_value = {
                "success": True,
                "summary": {"passed": 5, "failed": 0, "error": 0, "collected": 5},
                "test_results": None,
            }

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": True,
                "pylint": True,
                "mypy": True,
                "lint-imports": True,
            }

            result = registered_tools["run_pytest_check"]()

            assert "not available" not in result
            assert "All 5 tests passed" in result

    def test_resolved_python_passed_to_pytest_runner(self) -> None:
        """Verify that _resolved_python (not python_executable) is passed to the runner."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch("mcp_tools_py.checker_tools.check_code_with_pytest") as mock_check,
        ):
            registered_tools = _capture_tools(mock_fastmcp)
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            mock_check.return_value = {
                "success": True,
                "summary": {"passed": 1, "failed": 0, "error": 0, "collected": 1},
                "test_results": None,
            }

            server = _create_server(
                project_dir=Path("/project"),
                python_executable="/custom/python",
            )
            server._tool_availability = {
                "pytest": True,
                "pylint": True,
                "mypy": True,
                "lint-imports": True,
            }

            registered_tools["run_pytest_check"]()

            # Verify check_code_with_pytest was called with _resolved_python
            mock_check.assert_called_once()
            call_kwargs = mock_check.call_args
            assert call_kwargs.kwargs["python_executable"] == server._resolved_python
            assert call_kwargs.kwargs["python_executable"] == "/custom/python"

    def test_lint_imports_unavailable_returns_error(self) -> None:
        """When lint-imports is unavailable, tool handler returns error string."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
        ):
            registered_tools = _capture_tools(mock_fastmcp)
            mock_exec.return_value = make_command_result(return_code=0, stdout="ok")

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": True,
                "pylint": True,
                "mypy": True,
                "lint-imports": False,
            }
            server._lint_imports_binary = "/mock/venv/bin/lint-imports"

            result = registered_tools["run_lint_imports_check"]()

            assert "/mock/venv/bin/lint-imports" in result
            assert "lint-imports is not available" in result
