"""Tests that tool handlers short-circuit when their tool is unavailable."""

import os
from pathlib import Path
from unittest.mock import patch

from tests.test_tool_availability._helpers import _capture_tools, _create_server


class TestToolHandlerShortCircuit:
    """Test that tool handlers return immediate error when tool unavailable."""

    def test_pytest_unavailable_returns_error(self) -> None:
        """When pytest is unavailable, tool handler returns error string."""
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            registered_tools = _capture_tools(mock_fastmcp)

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": False,
                "pylint": True,
                "mypy": True,
                "black": True,
                "isort": True,
                "lint-imports": False,
                "ruff": True,
            }

            result = registered_tools["run_pytest_check"]()

            assert "pytest is not available" in result
            assert "Restart the server" in result

    def test_pylint_unavailable_returns_error(self) -> None:
        """When pylint is unavailable, tool handler returns error string."""
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            registered_tools = _capture_tools(mock_fastmcp)

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": True,
                "pylint": False,
                "mypy": True,
                "black": True,
                "isort": True,
                "lint-imports": False,
                "ruff": True,
            }

            result = registered_tools["run_pylint_check"]()

            assert "pylint is not available" in result
            assert "Restart the server" in result

    def test_mypy_unavailable_returns_error(self) -> None:
        """When mypy is unavailable, tool handler returns error string."""
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            registered_tools = _capture_tools(mock_fastmcp)

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": True,
                "pylint": True,
                "mypy": False,
                "black": True,
                "isort": True,
                "lint-imports": False,
                "ruff": True,
            }

            result = registered_tools["run_mypy_check"]()

            assert "mypy is not available" in result
            assert "Restart the server" in result

    def test_available_tool_runs_normally(self) -> None:
        """When tool is available, normal execution proceeds."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(
                "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
            ) as mock_check,
        ):
            registered_tools = _capture_tools(mock_fastmcp)

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
                "black": True,
                "isort": True,
                "lint-imports": True,
                "ruff": True,
            }

            result = registered_tools["run_pytest_check"]()

            assert "not available" not in result
            assert "All 5 tests passed" in result

    def test_resolved_python_passed_to_pytest_runner(self) -> None:
        """Verify that _resolved_python (not python_executable) is passed to the runner."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(
                "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
            ) as mock_check,
            patch(
                "mcp_tools_py.utils.python_environment.os.path.exists",
                return_value=True,
            ),
        ):
            registered_tools = _capture_tools(mock_fastmcp)

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
                "black": True,
                "isort": True,
                "lint-imports": True,
                "ruff": True,
            }

            registered_tools["run_pytest_check"]()

            # Verify check_code_with_pytest was called with _resolved_python
            mock_check.assert_called_once()
            call_kwargs = mock_check.call_args
            assert call_kwargs.kwargs["python_executable"] == server._resolved_python
            assert call_kwargs.kwargs["python_executable"] == str(
                Path("/custom/python")
            )

    def test_venv_bin_derived_from_resolved_python(self) -> None:
        """The PATH prepend follows the interpreter, not `--venv-path`."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(
                "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
            ) as mock_check,
            patch(
                "mcp_tools_py.utils.python_environment.os.path.exists",
                return_value=True,
            ),
        ):
            registered_tools = _capture_tools(mock_fastmcp)

            mock_check.return_value = {
                "success": True,
                "summary": {"passed": 1, "failed": 0, "error": 0, "collected": 1},
                "test_results": None,
            }

            server = _create_server(
                project_dir=Path("/project"),
                python_executable="/custom/python",
            )
            server._tool_availability = {"pytest": True}

            registered_tools["run_pytest_check"]()

            venv_bin = mock_check.call_args.kwargs["venv_bin"]
            assert venv_bin == os.path.dirname(server._resolved_python)
            assert venv_bin == str(Path("/custom"))

    def test_lint_imports_unavailable_returns_error(self) -> None:
        """When lint-imports is unavailable, tool handler returns error string."""
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            registered_tools = _capture_tools(mock_fastmcp)

            server = _create_server(project_dir=Path("/project"))
            server._tool_availability = {
                "pytest": True,
                "pylint": True,
                "mypy": True,
                "black": True,
                "isort": True,
                "lint-imports": False,
                "ruff": True,
            }

            result = registered_tools["run_lint_imports_check"]()

            assert os.path.dirname(server._resolved_python) in result
            assert "lint-imports is not available" in result
