"""Tests that tool handlers short-circuit when their tool is unavailable."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.conftest import make_environment_info
from tests.test_tool_availability._helpers import (
    _capture_tools,
    _create_server,
    _dummy_python,
)

_GET_ENVIRONMENT_INFO = "mcp_tools_py.utils.tool_context.get_environment_info"
_PYTEST_RUNNER = "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"


class TestToolHandlerShortCircuit:
    """Test that tool handlers return immediate error when tool unavailable."""

    def _server_with(self, tmp_path: Path, **importable: bool) -> tuple[Any, Any]:
        """Build a server over a pinned environment reporting `importable`.

        Returns:
            The server and the dict of tools it registered.
        """
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            registered_tools = _capture_tools(mock_fastmcp)
            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )
        return server, registered_tools

    def test_pytest_unavailable_returns_error(self, tmp_path: Path) -> None:
        """When pytest is unavailable, tool handler returns error string."""
        _, tools = self._server_with(tmp_path)

        with patch(
            _GET_ENVIRONMENT_INFO, return_value=make_environment_info(pytest=False)
        ):
            result = tools["run_pytest_check"]()

        assert "pytest is not available" in result
        assert "Restart the server" in result

    def test_pylint_unavailable_returns_error(self, tmp_path: Path) -> None:
        """When pylint is unavailable, tool handler returns error string."""
        _, tools = self._server_with(tmp_path)

        with patch(
            _GET_ENVIRONMENT_INFO, return_value=make_environment_info(pylint=False)
        ):
            result = tools["run_pylint_check"]()

        assert "pylint is not available" in result
        assert "Restart the server" in result

    def test_mypy_unavailable_returns_error(self, tmp_path: Path) -> None:
        """When mypy is unavailable, tool handler returns error string."""
        _, tools = self._server_with(tmp_path)

        with patch(
            _GET_ENVIRONMENT_INFO, return_value=make_environment_info(mypy=False)
        ):
            result = tools["run_mypy_check"]()

        assert "mypy is not available" in result
        assert "Restart the server" in result

    def test_available_tool_runs_normally(
        self, tmp_path: Path, all_modules_importable: Any
    ) -> None:
        """When tool is available, normal execution proceeds."""
        _, tools = self._server_with(tmp_path)

        with patch(_PYTEST_RUNNER) as mock_check:
            mock_check.return_value = {
                "success": True,
                "summary": {"passed": 5, "failed": 0, "error": 0, "collected": 5},
                "test_results": None,
            }
            result = tools["run_pytest_check"]()

        assert "not available" not in result
        assert "All 5 tests passed" in result

    def test_resolved_interpreter_passed_to_pytest_runner(
        self, all_modules_importable: Any
    ) -> None:
        """The interpreter the context resolved is passed to the runner."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(_PYTEST_RUNNER) as mock_check,
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

            registered_tools["run_pytest_check"]()

            mock_check.assert_called_once()
            call_kwargs = mock_check.call_args
            assert call_kwargs.kwargs["python_executable"] == str(
                server.context.environment.interpreter
            )
            assert call_kwargs.kwargs["python_executable"] == str(
                Path("/custom/python")
            )

    def test_venv_bin_derived_from_resolved_python(
        self, all_modules_importable: Any
    ) -> None:
        """The PATH prepend follows the interpreter, not `--venv-path`."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(_PYTEST_RUNNER) as mock_check,
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

            registered_tools["run_pytest_check"]()

            venv_bin = mock_check.call_args.kwargs["venv_bin"]
            assert venv_bin == str(server.context.environment.bin_dir)
            assert venv_bin == str(Path("/custom"))

    def test_lint_imports_unavailable_returns_error(self, tmp_path: Path) -> None:
        """When lint-imports is unavailable, tool handler returns error string."""
        server, tools = self._server_with(tmp_path)

        result = tools["run_lint_imports_check"]()

        assert str(server.context.environment.bin_dir) in result
        assert "lint-imports is not available" in result
