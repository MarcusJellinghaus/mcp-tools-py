"""Tests for the eager _check_tool_availability pass at server startup."""

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.test_tool_availability._helpers import _create_server, _dummy_python


class TestCheckToolAvailability:
    """Test _check_tool_availability caching."""

    def test_all_tools_available(self) -> None:
        """When all file-existence tools exist, all should be True."""
        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch(
                "mcp_tools_py.utils.python_environment.os.path.exists",
                return_value=True,
            ),
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
            patch("mcp_tools_py.utils.python_environment._IS_WINDOWS", True),
            patch(
                "mcp_tools_py.utils.python_environment.os.path.exists",
                return_value=True,
            ),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(project_dir=project_dir, venv_path="/mock/venv")

            assert server._tool_availability["lint-imports"] is True
            assert server._tool_binaries["lint-imports"] == str(
                Path("/mock/venv") / "Scripts" / "lint-imports.exe"
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

        def exists_side_effect(path: Path) -> bool:
            # Python executable exists, but lint-imports and vulture do not
            if "python" in str(path).lower():
                return True
            return False

        with (
            patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp,
            patch("mcp_tools_py.utils.python_environment._IS_WINDOWS", True),
            patch(
                "mcp_tools_py.utils.python_environment.os.path.exists",
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
            patch("mcp_tools_py.utils.python_environment._IS_WINDOWS", True),
            patch(
                "mcp_tools_py.utils.python_environment.os.path.exists",
                return_value=True,
            ),
        ):
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            server = _create_server(project_dir=project_dir, venv_path="/mock/venv")

            assert server._tool_availability["vulture"] is True
            assert server._tool_binaries["vulture"] == str(
                Path("/mock/venv") / "Scripts" / "vulture.exe"
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

    def test_startup_warning_matches_handler_message(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The startup warning is the handler's message, distribution included."""
        with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
            mock_fastmcp.return_value.tool.return_value = MagicMock()

            with caplog.at_level(logging.WARNING, logger="mcp_tools_py.server"):
                server = _create_server(
                    project_dir=Path("/project"),
                    python_executable=_dummy_python(tmp_path),
                )

            warnings = [record.getMessage() for record in caplog.records]
            assert server.tool_unavailable_message("ruff") in warnings
            assert server.tool_unavailable_message("lint-imports") in warnings
            assert any("import-linter is installed" in text for text in warnings)

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
