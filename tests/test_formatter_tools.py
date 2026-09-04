"""Tests for FormatterTools MCP tool registration and logic."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.formatter.formatter_tools import FormatterTools, _format_results
from mcp_tools_py.formatter.models import FormatterResult


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
    server._is_tool_available = lambda tool: server._tool_availability.get(tool, False)
    server.tool_unavailable_message = lambda key: (
        f"{key} is not available in /mock/venv/bin. "
        "Restart the server after installing."
    )
    server.resolve_timeout = lambda tool, explicit=None: (
        300 if tool == "pytest" else 120
    )
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


def _make_formatter_result(
    output: str = "output",
    success: bool = True,
    unparsable_files: list[str] | None = None,
) -> FormatterResult:
    return FormatterResult(
        output=output,
        success=success,
        files_changed=[],
        unparsable_files=list(unparsable_files or []),
    )


_RUNNER_PATCH = "mcp_tools_py.formatter.formatter_tools._run_format_code"


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
        """Call with no args, verify steps passed through to runner."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(output="isort output"),
                "black": _make_formatter_result(output="black output"),
            }
        )

        with patch(_RUNNER_PATCH, mock_runner):
            result = run_format(target_directories=["src"])

        # Default steps=None passed through
        mock_runner.assert_called_once()
        assert "## isort" in result
        assert "## black" in result

    def test_custom_steps_order(self, mock_server: MagicMock) -> None:
        """Pass steps=["black"], verify only black in output."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "black": _make_formatter_result(output="black output"),
            }
        )

        with patch(_RUNNER_PATCH, mock_runner):
            result = run_format(steps=["black"], target_directories=["src"])

        assert "## black" in result
        assert "## isort" not in result


class TestValidation:
    """Tests for input validation."""

    def test_runner_value_error_returns_error(self, mock_server: MagicMock) -> None:
        """Runner raises ValueError, wrapper returns error string."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(side_effect=ValueError("bad timeout"))

        with patch(_RUNNER_PATCH, mock_runner):
            result = run_format(steps=["black"], target_directories=["src"])

        assert "Error" in result
        assert "bad timeout" in result

    def test_unknown_step_reported_as_invalid_not_missing(
        self, mock_server: MagicMock
    ) -> None:
        """An unknown step is rejected before the availability check runs."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock()

        with patch(_RUNNER_PATCH, mock_runner):
            result = run_format(steps=["foo"], target_directories=["src"])

        mock_runner.assert_not_called()
        assert "Invalid formatter steps: ['foo']" in result
        assert "not available" not in result
        assert "console script" not in result


class TestTargetDirectories:
    """Tests for target directory resolution."""

    def test_target_directories_auto_detected(self, mock_server: MagicMock) -> None:
        """Mock resolve_target_directories, verify it's called when target_directories=None."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(),
                "black": _make_formatter_result(),
            }
        )

        with (
            patch(
                "mcp_tools_py.formatter.formatter_tools.resolve_target_directories",
                return_value=["src"],
            ) as mock_resolve,
            patch(_RUNNER_PATCH, mock_runner),
        ):
            run_format()

        mock_resolve.assert_called_once_with(str(mock_server.project_dir), None)

    def test_target_directories_explicit(self, mock_server: MagicMock) -> None:
        """Pass explicit dirs, verify resolve_target_directories receives them."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(),
                "black": _make_formatter_result(),
            }
        )

        with (
            patch(
                "mcp_tools_py.formatter.formatter_tools.resolve_target_directories",
                return_value=["src", "tests"],
            ) as mock_resolve,
            patch(_RUNNER_PATCH, mock_runner),
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
        """check_only with failures — both steps in output, no 'stopped' message."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(
                    output="needs formatting", success=False
                ),
                "black": _make_formatter_result(
                    output="needs formatting", success=False
                ),
            }
        )

        with patch(_RUNNER_PATCH, mock_runner):
            result = run_format(target_directories=["src"], check_only=True)

        assert "## isort" in result
        assert "## black" in result
        assert "Formatting stopped" not in result

    def test_normal_mode_stops_on_first_failure(self, mock_server: MagicMock) -> None:
        """isort fails in runner, only isort in results → stopped message."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(output="error output", success=False),
            }
        )

        with patch(_RUNNER_PATCH, mock_runner):
            result = run_format(target_directories=["src"])

        assert "## isort" in result
        assert "Formatting stopped" in result
        assert "## black" not in result


class TestOutput:
    """Tests for output formatting."""

    def test_output_has_markdown_headers(self, mock_server: MagicMock) -> None:
        """Verify output contains ## isort and ## black."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(output="some output"),
                "black": _make_formatter_result(output="some output"),
            }
        )

        with patch(_RUNNER_PATCH, mock_runner):
            result = run_format(target_directories=["src"])

        assert "## isort" in result
        assert "## black" in result

    def test_unparsable_files_rendered_above_raw_output(self) -> None:
        """11 unparsable paths — block, cap at 10, and remainder line."""
        paths = [f"src\\pkg\\module_{i}.py" for i in range(11)]
        results = {
            "isort": _make_formatter_result(
                output="raw isort output", unparsable_files=paths
            )
        }

        result = _format_results(results, ["isort"], check_only=True)

        assert result.startswith("## isort")
        assert "ERROR: isort could not read 11 file(s)" in result
        assert paths[0] in result
        assert paths[9] in result
        assert paths[10] not in result
        assert "... and 1 more" in result
        assert result.index(paths[0]) < result.index("raw isort output")


class TestTimeouts:
    """Tests for timeout resolution."""

    def test_resolved_timeouts_passed_to_runner(self, mock_server: MagicMock) -> None:
        """Both black and isort budgets are resolved and forwarded."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(),
                "black": _make_formatter_result(),
            }
        )

        with patch(_RUNNER_PATCH, mock_runner):
            run_format(target_directories=["src"])

        assert mock_runner.call_args[1]["timeouts"] == {"isort": 120, "black": 120}


class TestToolAvailability:
    """Tests for tool availability checking."""

    def test_tool_unavailable_returns_error(self, mock_server: MagicMock) -> None:
        """black not available, verify error before runner is called."""
        mock_server._tool_availability = {"isort": True, "black": False}
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock()

        with patch(_RUNNER_PATCH, mock_runner):
            result = run_format(target_directories=["src"])

        # Runner should NOT have been called
        mock_runner.assert_not_called()
        assert "black is not available" in result


_CONFLICT_PATCH = "mcp_tools_py.formatter.formatter_tools.check_line_length_conflicts"


class TestLineLengthWarnings:
    """Tests for line-length conflict warning integration."""

    def test_line_length_warnings_prepended(self, mock_server: MagicMock) -> None:
        """Warnings from check_line_length_conflicts appear before formatter output."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(output="isort output"),
                "black": _make_formatter_result(output="black output"),
            }
        )

        with (
            patch(_RUNNER_PATCH, mock_runner),
            patch(
                _CONFLICT_PATCH,
                return_value=[
                    "Line-length mismatch: black=88, isort=120. Formatting may be inconsistent."
                ],
            ),
        ):
            result = run_format(target_directories=["src"])

        # Warning should appear before formatter sections
        warning_pos = result.index("Line-length mismatch")
        isort_pos = result.index("## isort")
        assert warning_pos < isort_pos

    def test_no_line_length_warnings(self, mock_server: MagicMock) -> None:
        """No warnings → no extra text prepended."""
        run_format = _capture_run_format_code(mock_server)

        mock_runner = MagicMock(
            return_value={
                "isort": _make_formatter_result(output="isort output"),
                "black": _make_formatter_result(output="black output"),
            }
        )

        with (
            patch(_RUNNER_PATCH, mock_runner),
            patch(_CONFLICT_PATCH, return_value=[]),
        ):
            result = run_format(target_directories=["src"])

        assert "mismatch" not in result.lower()
        assert result.startswith("## isort")
