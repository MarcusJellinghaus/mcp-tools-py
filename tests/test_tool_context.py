"""Tests for ToolContext: availability, messages and timeout resolution."""

import dataclasses
import json
import logging
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_tools_py.utils.environment_info import PROBED_MODULES
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.tool_context import CONSOLE_SCRIPT_TOOLS, ToolContext
from tests.conftest import make_command_result, make_environment_info
from tests.test_tool_availability._helpers import _dummy_python

_GET_ENVIRONMENT_INFO = "mcp_tools_py.utils.tool_context.get_environment_info"
_EXECUTE_COMMAND = "mcp_tools_py.utils.environment_info.execute_command"
_LOGGER = "mcp_tools_py.utils.tool_context"


def _context(
    tmp_path: Path, *scripts: str, check_timeout: int | None = None
) -> ToolContext:
    """Build a context whose script directory holds exactly `scripts`.

    Returns:
        A ToolContext over a pinned dummy environment.
    """
    interpreter = _dummy_python(tmp_path, *scripts)
    return ToolContext(
        project_dir=tmp_path,
        environment=PythonEnvironment(Path(interpreter)),
        check_timeout=check_timeout,
    )


def _probe_stdout() -> str:
    """Build the JSON a successful probe writes, with every module importable.

    Returns:
        The probe's stdout as a JSON string.
    """
    return json.dumps(
        {
            "version": "3.11.9",
            "sys_path": [],
            "distributions": {},
            "importable": {module: True for module in PROBED_MODULES},
        }
    )


class TestIsToolAvailableConsoleScripts:
    """A console-script tool is a filesystem question, never a probe."""

    @pytest.mark.parametrize("tool_name", sorted(CONSOLE_SCRIPT_TOOLS))
    def test_present_then_absent(self, tmp_path: Path, tool_name: str) -> None:
        """The answer follows the console script on disk, and no probe runs."""
        context = _context(tmp_path, tool_name)

        with patch(_GET_ENVIRONMENT_INFO) as mock_info:
            assert context.is_tool_available(tool_name) is True

            binary = context.environment.binary(tool_name)
            assert binary is not None
            binary.unlink()

            assert context.is_tool_available(tool_name) is False
            mock_info.assert_not_called()


class TestIsToolAvailableModules:
    """A `python -m` tool is answered by the one-shot environment probe."""

    def test_importable_module_is_available(self, tmp_path: Path) -> None:
        """A probe reporting the module importable means available."""
        context = _context(tmp_path)

        with patch(_GET_ENVIRONMENT_INFO, return_value=make_environment_info()):
            assert context.is_tool_available("pytest") is True

    def test_missing_module_is_unavailable(self, tmp_path: Path) -> None:
        """A probe reporting the module missing means unavailable."""
        context = _context(tmp_path)

        with patch(
            _GET_ENVIRONMENT_INFO, return_value=make_environment_info(pytest=False)
        ):
            assert context.is_tool_available("pytest") is False

    def test_missing_module_warning_names_installed_distribution(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A missing module whose distribution is installed reads as broken."""
        context = _context(tmp_path)

        with (
            patch(
                _GET_ENVIRONMENT_INFO,
                return_value=make_environment_info(
                    distributions={"pytest": "8.0.0"}, pytest=False
                ),
            ),
            caplog.at_level(logging.WARNING, logger=_LOGGER),
        ):
            assert context.is_tool_available("pytest") is False

        assert any(
            "pytest 8.0.0" in record.getMessage() and "broken" in record.getMessage()
            for record in caplog.records
        )

    def test_failed_probe_fails_open_and_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A probe that could not be trusted reports the tool available."""
        context = _context(tmp_path)

        with (
            patch(
                _EXECUTE_COMMAND,
                return_value=make_command_result(
                    return_code=-1,
                    timed_out=True,
                    execution_error="Process timed out after 30 seconds",
                ),
            ),
            caplog.at_level(logging.WARNING, logger=_LOGGER),
        ):
            assert context.is_tool_available("pytest") is True

        assert any(
            "timed out" in record.getMessage() and "pytest" in record.getMessage()
            for record in caplog.records
        )

    def test_second_call_runs_no_further_subprocess(self, tmp_path: Path) -> None:
        """The probe cache lives in get_environment_info, not on any caller."""
        context = _context(tmp_path)

        with patch(
            _EXECUTE_COMMAND, return_value=make_command_result(stdout=_probe_stdout())
        ) as mock_exec:
            assert context.is_tool_available("pytest") is True
            assert context.is_tool_available("mypy") is True

        mock_exec.assert_called_once()


class TestUnavailableMessage:
    """Test the two unavailable-tool message templates."""

    def test_script_tool_message_reports_directory(self, tmp_path: Path) -> None:
        """A console-script tool names the directory searched, never 'N/A'."""
        context = _context(tmp_path)

        message = context.unavailable_message("ruff")

        assert "ruff is not available" in message
        assert str(context.environment.bin_dir) in message
        assert "Restart the server" in message
        assert "N/A" not in message
        assert "--venv-path" not in message

    def test_probe_tool_message_reports_interpreter(self, tmp_path: Path) -> None:
        """A `python -m` tool names the resolved interpreter and its version."""
        context = _context(tmp_path)

        with patch(
            _GET_ENVIRONMENT_INFO,
            return_value=make_environment_info(version="3.12.1", pytest=False),
        ):
            message = context.unavailable_message("pytest")

        assert "pytest is not available" in message
        assert str(context.environment.interpreter) in message
        assert "Python 3.12.1" in message
        assert "--python-executable" in message
        assert "Restart the server" in message
        assert "--venv-path" not in message

    def test_probe_tool_message_reports_broken_install(self, tmp_path: Path) -> None:
        """An installed distribution that will not import is named as broken."""
        context = _context(tmp_path)

        with patch(
            _GET_ENVIRONMENT_INFO,
            return_value=make_environment_info(
                distributions={"mypy": "1.15.0"}, mypy=False
            ),
        ):
            message = context.unavailable_message("mypy")

        assert "mypy 1.15.0 is installed there" in message
        assert "broken" in message

    def test_lint_imports_message_names_import_linter(self, tmp_path: Path) -> None:
        """The package map names the distribution, not the tool."""
        context = _context(tmp_path)

        message = context.unavailable_message("lint-imports")

        assert "lint-imports is not available" in message
        assert "import-linter is installed" in message

    def test_unmapped_tool_installs_under_its_own_name(self, tmp_path: Path) -> None:
        """A tool absent from the package map is installed under its key."""
        context = _context(tmp_path)

        message = context.unavailable_message("ruff")

        assert "ruff is installed" in message


class TestResolveTimeout:
    """Tests for ToolContext.resolve_timeout."""

    def test_cli_timeout_applies_to_every_tool(self, tmp_path: Path) -> None:
        """check_timeout from the CLI overrides both built-in defaults."""
        context = _context(tmp_path, check_timeout=45)

        assert context.resolve_timeout("mypy") == 45
        assert context.resolve_timeout("pytest") == 45

    def test_built_in_defaults_without_configuration(self, tmp_path: Path) -> None:
        """Without configuration, pytest gets 300 and everything else 120."""
        context = _context(tmp_path)

        assert context.resolve_timeout("mypy") == 120
        assert context.resolve_timeout("pytest") == 300

    def test_pyproject_value_beats_cli_timeout(self, tmp_path: Path) -> None:
        """A per-tool pyproject value wins over --check-timeout."""
        (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""\
                [tool.mcp-tools-py]
                mypy-timeout = 600
                """))
        context = _context(tmp_path, check_timeout=45)

        assert context.resolve_timeout("mypy") == 600
        assert context.resolve_timeout("pylint") == 45

    def test_explicit_argument_wins(self, tmp_path: Path) -> None:
        """An explicit per-call value beats the server-level timeout."""
        context = _context(tmp_path, check_timeout=45)

        assert context.resolve_timeout("mypy", 90) == 90


def test_context_is_frozen(tmp_path: Path) -> None:
    """A registrar cannot rewrite what the server configured."""
    context = _context(tmp_path)

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.test_folder = "other"  # type: ignore[misc]
