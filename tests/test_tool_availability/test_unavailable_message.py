"""Tests for the two unavailable-tool message templates."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from tests.test_tool_availability._helpers import _create_server, _dummy_python


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

    def test_lint_imports_package_defaults_without_override(
        self, tmp_path: Path
    ) -> None:
        """The distribution name is looked up when no override is passed."""
        server = self._server(tmp_path)

        message = server.tool_unavailable_message("lint-imports")

        assert "import-linter is installed" in message
