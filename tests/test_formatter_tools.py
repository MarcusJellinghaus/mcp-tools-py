"""Tests for FormatterTools MCP tool registration and logic."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.formatter.formatter_tools import FormatterTools


@pytest.fixture
def mock_server() -> MagicMock:
    """Create a mock CodeCheckerServer with required attributes."""
    server = MagicMock()
    server.project_dir = Path("/fake/project")
    server._resolved_python = "/usr/bin/python3"
    server._tool_availability = {
        "isort": True,
        "black": True,
    }
    return server


def _capture_run_format_code(mock_server: MagicMock) -> Any:
    """Register FormatterTools and capture the run_format_code function."""
    captured_fns: dict[str, Any] = {}

    def capture(fn: Any) -> Any:
        captured_fns[fn.__name__] = fn
        return fn

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture
    FormatterTools(mock_server).register(mock_mcp)
    return captured_fns["run_format_code"]


class TestRegistration:
    """Tests for tool registration."""

    def test_registers_one_tool(self, mock_server: MagicMock) -> None:
        """Verify mcp.tool() called exactly once."""
        mock_mcp = MagicMock()
        mock_decorator = MagicMock(side_effect=lambda fn: fn)
        mock_mcp.tool.return_value = mock_decorator

        FormatterTools(mock_server).register(mock_mcp)

        assert mock_mcp.tool.call_count == 1


class TestStepOrdering:
    """Tests for step selection and ordering."""

    def test_default_steps_isort_then_black(self, mock_server: MagicMock) -> None:
        """Call with no args, verify isort runs before black."""
        run_format = _capture_run_format_code(mock_server)
        call_order: list[str] = []

        def fake_isort(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            call_order.append("isort")
            return "isort output", True

        def fake_black(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            call_order.append("black")
            return "black output", True

        with (
            patch(
                "mcp_tools_py.formatter.formatter_tools.run_isort",
                side_effect=fake_isort,
            ),
            patch(
                "mcp_tools_py.formatter.formatter_tools.run_black",
                side_effect=fake_black,
            ),
            patch(
                "mcp_tools_py.formatter.formatter_tools._STEP_RUNNERS",
                {"isort": fake_isort, "black": fake_black},
            ),
        ):
            result = run_format(target_directories=["src"])

        assert call_order == ["isort", "black"]
        assert "## isort" in result
        assert "## black" in result

    def test_custom_steps_order(self, mock_server: MagicMock) -> None:
        """Pass steps=["black"], verify only black runs."""
        run_format = _capture_run_format_code(mock_server)

        def fake_black(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            return "black output", True

        with patch(
            "mcp_tools_py.formatter.formatter_tools._STEP_RUNNERS",
            {"isort": MagicMock(), "black": fake_black},
        ):
            result = run_format(steps=["black"], target_directories=["src"])

        assert "## black" in result
        assert "## isort" not in result


class TestValidation:
    """Tests for input validation."""

    def test_invalid_step_returns_error(self, mock_server: MagicMock) -> None:
        """Pass steps=["ruff"], verify error returned."""
        run_format = _capture_run_format_code(mock_server)
        result = run_format(steps=["ruff"], target_directories=["src"])

        assert "Error" in result
        assert "ruff" in result


class TestTargetDirectories:
    """Tests for target directory resolution."""

    def test_target_directories_auto_detected(self, mock_server: MagicMock) -> None:
        """Mock resolve_target_directories, verify it's called when target_directories=None."""
        run_format = _capture_run_format_code(mock_server)

        def fake_runner(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            return "output", True

        with (
            patch(
                "mcp_tools_py.formatter.formatter_tools.resolve_target_directories",
                return_value=["src"],
            ) as mock_resolve,
            patch(
                "mcp_tools_py.formatter.formatter_tools._STEP_RUNNERS",
                {"isort": fake_runner, "black": fake_runner},
            ),
        ):
            run_format()

        mock_resolve.assert_called_once_with(str(mock_server.project_dir), None)

    def test_target_directories_explicit(self, mock_server: MagicMock) -> None:
        """Pass explicit dirs, verify resolve_target_directories returns them directly."""
        run_format = _capture_run_format_code(mock_server)

        def fake_runner(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            return "output", True

        with (
            patch(
                "mcp_tools_py.formatter.formatter_tools.resolve_target_directories",
                return_value=["src", "tests"],
            ) as mock_resolve,
            patch(
                "mcp_tools_py.formatter.formatter_tools._STEP_RUNNERS",
                {"isort": fake_runner, "black": fake_runner},
            ),
        ):
            run_format(target_directories=["src", "tests"])

        mock_resolve.assert_called_once_with(
            str(mock_server.project_dir), ["src", "tests"]
        )


class TestCheckOnlyMode:
    """Tests for check_only behavior."""

    def test_check_only_runs_all_steps_despite_nonzero(
        self, mock_server: MagicMock
    ) -> None:
        """isort returns success=False (needs formatting), black still runs."""
        run_format = _capture_run_format_code(mock_server)
        call_order: list[str] = []

        def fake_isort(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            call_order.append("isort")
            return "needs formatting", False

        def fake_black(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            call_order.append("black")
            return "needs formatting", False

        with patch(
            "mcp_tools_py.formatter.formatter_tools._STEP_RUNNERS",
            {"isort": fake_isort, "black": fake_black},
        ):
            result = run_format(target_directories=["src"], check_only=True)

        assert call_order == ["isort", "black"]
        assert "## isort" in result
        assert "## black" in result
        assert "Formatting stopped" not in result

    def test_normal_mode_stops_on_first_failure(self, mock_server: MagicMock) -> None:
        """isort returns success=False, black does NOT run."""
        run_format = _capture_run_format_code(mock_server)
        call_order: list[str] = []

        def fake_isort(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            call_order.append("isort")
            return "error output", False

        def fake_black(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            call_order.append("black")
            return "black output", True

        with patch(
            "mcp_tools_py.formatter.formatter_tools._STEP_RUNNERS",
            {"isort": fake_isort, "black": fake_black},
        ):
            result = run_format(target_directories=["src"])

        assert call_order == ["isort"]
        assert "## isort" in result
        assert "Formatting stopped" in result
        assert "## black" not in result


class TestOutput:
    """Tests for output formatting."""

    def test_output_has_markdown_headers(self, mock_server: MagicMock) -> None:
        """Verify output contains ## isort and ## black."""
        run_format = _capture_run_format_code(mock_server)

        def fake_runner(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            return "some output", True

        with patch(
            "mcp_tools_py.formatter.formatter_tools._STEP_RUNNERS",
            {"isort": fake_runner, "black": fake_runner},
        ):
            result = run_format(target_directories=["src"])

        assert "## isort" in result
        assert "## black" in result


class TestToolAvailability:
    """Tests for tool availability checking."""

    def test_tool_unavailable_returns_error(self, mock_server: MagicMock) -> None:
        """black not in _tool_availability, verify error message."""
        mock_server._tool_availability = {"isort": True, "black": False}
        run_format = _capture_run_format_code(mock_server)

        def fake_isort(*_args: Any, **_kwargs: Any) -> tuple[str, bool]:
            return "isort output", True

        with patch(
            "mcp_tools_py.formatter.formatter_tools._STEP_RUNNERS",
            {"isort": fake_isort, "black": MagicMock()},
        ):
            result = run_format(target_directories=["src"])

        assert "black is not available" in result
