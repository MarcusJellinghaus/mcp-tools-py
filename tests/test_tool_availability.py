"""Tests for startup tool validation: _resolve_python_executable and _check_tool_availability."""

import logging
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_command_result


def _create_server(**kwargs: Any) -> Any:
    """Create a ToolServer with mocked FastMCP and execute_command."""
    from mcp_tools_py.server import ToolServer

    return ToolServer(**kwargs)


def _dummy_python(tmp_path: Path, *scripts: str) -> str:
    """Create a script directory with a dummy interpreter and console scripts.

    Pins the directory that availability detection searches, so tests do not
    depend on what the ambient interpreter happens to have installed.

    Returns:
        Path to the dummy interpreter, for passing as `python_executable`.
    """
    script_dir = tmp_path / "scripts"
    script_dir.mkdir(exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    python = script_dir / f"python{suffix}"
    python.write_text("")
    for name in scripts:
        (script_dir / f"{name}{suffix}").write_text("")
    return str(python)


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


# ---------------------------------------------------------------------------
# _check_tool_availability tests
# ---------------------------------------------------------------------------


class TestCheckToolAvailability:
    """Test _check_tool_availability caching."""

    def test_all_tools_available(self) -> None:
        """When all file-existence tools exist, all should be True."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"), venv_path="/mock/venv"
            )

            assert server._tool_availability == {
                "lint-imports": True,
                "vulture": True,
                "ruff": True,
                "bandit": True,
                "tach": True,
            }

    def test_all_tools_missing(self, tmp_path: Path) -> None:
        """When no console script sits next to the interpreter, all five are False."""
        with (patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

            assert server._tool_availability == {
                "lint-imports": False,
                "vulture": False,
                "ruff": False,
                "bandit": False,
                "tach": False,
            }
            assert server._tool_binaries == {}

    def test_lint_imports_available_when_binary_exists(self) -> None:
        """When venv_path is set and lint-imports binary exists, mark available."""
        project_dir = Path("/project")
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.os.name", "nt"),
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(project_dir=project_dir, venv_path="/mock/venv")

            assert server._tool_availability["lint-imports"] is True
            assert server._tool_binaries["lint-imports"] == os.path.join(
                "/mock/venv", "Scripts", "lint-imports.exe"
            )
            assert "vulture" in server._tool_availability

    def test_lint_imports_unavailable_when_script_not_on_disk(
        self, tmp_path: Path
    ) -> None:
        """When no lint-imports console script is on disk, it is unavailable."""
        with (patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

            assert server._tool_availability["lint-imports"] is False
            assert "lint-imports" not in server._tool_binaries
            assert server._tool_availability["vulture"] is False
            assert server._tool_availability["tach"] is False
            assert "tach" not in server._tool_binaries

    def test_lint_imports_unavailable_when_binary_missing(self) -> None:
        """When venv_path is set but binary doesn't exist, mark unavailable."""
        project_dir = Path("/project")

        def exists_side_effect(path: str) -> bool:
            # Python executable exists, but lint-imports and vulture do not
            if "python" in path.lower():
                return True
            return False

        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.os.name", "nt"),
            patch(
                "mcp_tools_py.server.os.path.exists",
                side_effect=exists_side_effect,
            ),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(project_dir=project_dir, venv_path="/mock/venv")

            assert server._tool_availability["lint-imports"] is False
            assert "lint-imports" not in server._tool_binaries
            assert server._tool_availability["vulture"] is False
            assert "vulture" not in server._tool_binaries
            assert server._tool_availability["tach"] is False
            assert "tach" not in server._tool_binaries

    def test_vulture_available_when_binary_exists(self) -> None:
        """When venv_path is set and vulture binary exists, mark available."""
        project_dir = Path("/project")
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.os.name", "nt"),
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(project_dir=project_dir, venv_path="/mock/venv")

            assert server._tool_availability["vulture"] is True
            assert server._tool_binaries["vulture"] == os.path.join(
                "/mock/venv", "Scripts", "vulture.exe"
            )

    def test_vulture_unavailable_when_script_not_on_disk(self, tmp_path: Path) -> None:
        """When no vulture console script is on disk, it is unavailable."""
        with (patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

            assert server._tool_availability["vulture"] is False
            assert "vulture" not in server._tool_binaries
            assert server._tool_availability["tach"] is False
            assert "tach" not in server._tool_binaries

    def test_scripts_found_without_venv_path(self, tmp_path: Path) -> None:
        """Detection follows the resolved interpreter, not --venv-path."""
        python = _dummy_python(
            tmp_path, "lint-imports", "vulture", "ruff", "bandit", "tach"
        )
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(
                project_dir=Path("/project"),
                python_executable=python,
                venv_path=None,
            )

            suffix = ".exe" if os.name == "nt" else ""
            script_dir = os.path.dirname(python)
            for key in ("lint-imports", "vulture", "ruff", "bandit", "tach"):
                assert server._tool_availability[key] is True
                assert server._tool_binaries[key] == os.path.join(
                    script_dir, f"{key}{suffix}"
                )


# ---------------------------------------------------------------------------
# _is_tool_available tests
# ---------------------------------------------------------------------------


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
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
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


# ---------------------------------------------------------------------------
# tool_unavailable_message tests
# ---------------------------------------------------------------------------


class TestToolUnavailableMessage:
    """Test the two unavailable-tool message templates."""

    def _server(self, tmp_path: Path) -> Any:
        """Build a server whose script directory is pinned to tmp_path."""
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            mock_fastmcp.return_value.tool.return_value = MagicMock()
            return _create_server(
                project_dir=Path("/project"),
                python_executable=_dummy_python(tmp_path),
            )

    def test_script_tool_message_reports_directory(self, tmp_path: Path) -> None:
        """A console-script tool names the directory searched, never 'N/A'."""
        server = self._server(tmp_path)

        message = server.tool_unavailable_message("ruff")

        assert "ruff is not available" in message
        assert os.path.dirname(server._resolved_python) in message
        assert "Restart the server" in message
        assert "N/A" not in message
        assert "--venv-path" not in message

    def test_probe_tool_message_reports_interpreter(self, tmp_path: Path) -> None:
        """A `python -m` tool names the resolved interpreter."""
        server = self._server(tmp_path)

        message = server.tool_unavailable_message("pytest")

        assert "pytest is not available" in message
        assert server._resolved_python in message
        assert "--python-executable" in message
        assert "Restart the server" in message
        assert "--venv-path" not in message

    def test_lint_imports_message_names_import_linter(self, tmp_path: Path) -> None:
        """The package override names the distribution, not the tool."""
        server = self._server(tmp_path)

        message = server.tool_unavailable_message(
            "lint-imports", package="import-linter"
        )

        assert "lint-imports is not available" in message
        assert "import-linter is installed" in message


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
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch(
                "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
            ) as mock_check,
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
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch(
                "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
            ) as mock_check,
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
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
            assert call_kwargs.kwargs["python_executable"] == "/custom/python"

    def test_venv_bin_derived_from_resolved_python(self) -> None:
        """The PATH prepend follows the interpreter, not `--venv-path`."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.server.execute_command") as mock_exec,
            patch(
                "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
            ) as mock_check,
            patch("mcp_tools_py.server.os.path.exists", return_value=True),
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
            assert server.venv_path is None
            server._tool_availability = {"pytest": True}

            registered_tools["run_pytest_check"]()

            venv_bin = mock_check.call_args.kwargs["venv_bin"]
            assert venv_bin == os.path.dirname(server._resolved_python)
            assert venv_bin == "/custom"

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
                "black": True,
                "isort": True,
                "lint-imports": False,
                "ruff": True,
            }

            result = registered_tools["run_lint_imports_check"]()

            assert os.path.dirname(server._resolved_python) in result
            assert "lint-imports is not available" in result
