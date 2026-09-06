"""Unit tests for inspect_library: the parent side, and real resolution."""

import sys
from unittest.mock import patch

import pytest

from mcp_tools_py.inspect_library import SOURCE_TIMEOUT_SECONDS, _get_library_source
from mcp_tools_py.utils.environment_info import probe_script_path
from tests.conftest import make_command_result


def _src(import_path: str, max_lines: int = 200) -> str:
    """Resolve `import_path` in the interpreter running the tests.

    Args:
        import_path: Dotted import path to resolve.
        max_lines: Maximum source lines to return.

    Returns:
        The tool's answer for that path.
    """
    return _get_library_source(import_path, max_lines, sys.executable)


class TestArgumentHandling:
    """Tests for arguments the parent answers without a child process."""

    @pytest.mark.parametrize("bad_value", [0, -5, -1])
    def test_max_lines_invalid_returns_error(self, bad_value: int) -> None:
        """max_lines in [0, -5, -1] → validation error."""
        result = _src("anything", max_lines=bad_value)

        assert (
            f"max_lines must be a positive integer (>= 1), got: {bad_value}" == result
        )

    @pytest.mark.parametrize("bad_path", ["", ".", ".."])
    def test_empty_or_malformed_import_path(self, bad_path: str) -> None:
        """Empty or malformed import paths return error instead of raising."""
        result = _src(bad_path)

        assert "not found" in result.lower()


class TestChildProcess:
    """Tests for how the parent treats the child process it runs."""

    def test_timeout_names_the_import_path(self) -> None:
        """A child that times out yields a message, not an exception."""
        with patch("mcp_tools_py.inspect_library.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=-1,
                timed_out=True,
                execution_error="Process timed out",
            )

            result = _get_library_source("json.encoder", 200, "/some/python")

            assert "json.encoder" in result
            assert "timed out" in result
            assert str(SOURCE_TIMEOUT_SECONDS) in result

    def test_non_zero_exit_reports_code_and_stderr(self) -> None:
        """A child that crashes yields its exit code and a stderr snippet."""
        with patch("mcp_tools_py.inspect_library.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=1, stderr="Traceback: boom"
            )

            result = _get_library_source("json.encoder", 200, "/some/python")

            assert "json.encoder" in result
            assert "1" in result
            assert "Traceback: boom" in result

    def test_missing_interpreter_names_the_interpreter(self) -> None:
        """An interpreter that cannot be run is named in the message."""
        with patch("mcp_tools_py.inspect_library.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                return_code=-1, execution_error="No such file or directory"
            )

            result = _get_library_source("json.encoder", 200, "/no/such/python")

            assert "/no/such/python" in result
            assert "No such file or directory" in result

    def test_stdout_returned_verbatim(self) -> None:
        """The child's output is the tool's output, unchanged."""
        with patch("mcp_tools_py.inspect_library.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(
                stdout="def foo():\n    return 42\n"
            )

            result = _get_library_source("mod.foo", 200, "/some/python")

            assert result == "def foo():\n    return 42\n"

    def test_invalid_max_lines_runs_no_child(self) -> None:
        """Argument validation needs no environment, so it costs no subprocess."""
        with patch("mcp_tools_py.inspect_library.execute_command") as mock_exec:
            _get_library_source("json.encoder", 0, "/some/python")

            mock_exec.assert_not_called()

    def test_command_uses_the_given_interpreter(self) -> None:
        """The command runs the probe under the interpreter passed in."""
        with patch("mcp_tools_py.inspect_library.execute_command") as mock_exec:
            mock_exec.return_value = make_command_result(stdout="source")

            _get_library_source("json.encoder", 50, "/some/python")

            command = mock_exec.call_args.args[0]
            assert command == [
                "/some/python",
                str(probe_script_path()),
                "source",
                "json.encoder",
                "50",
            ]


class TestRealImports:
    """Real-import tests against actual installed packages (no mocking)."""

    def test_stdlib_class(self) -> None:
        """json.encoder.JSONEncoder resolves to the real class source."""
        result = _src("json.encoder.JSONEncoder")

        assert "def encode" in result

    def test_module_level(self) -> None:
        """json.encoder resolves to the full module source."""
        result = _src("json.encoder")

        assert "class JSONEncoder" in result

    def test_nested_attribute(self) -> None:
        """json.encoder.JSONEncoder.encode resolves to just the method."""
        method_source = _src("json.encoder.JSONEncoder.encode")
        class_source = _src("json.encoder.JSONEncoder")

        assert "def encode" in method_source
        assert len(method_source) < len(class_source)

    def test_custom_max_lines_truncation(self) -> None:
        """JSONEncoder source is truncated when max_lines=50."""
        result = _src("json.encoder.JSONEncoder", max_lines=50)

        assert "truncated" in result
        assert "showing 50 of" in result

    def test_bad_module(self) -> None:
        """Completely unknown package returns 'not found'."""
        result = _src("nonexistent_package.Foo")

        assert "not found" in result

    def test_bad_symbol_lists_available(self) -> None:
        """Known module + bad symbol lists available symbols with types."""
        result = _src("json.NoSuchThing")

        assert "not found in module" in result
        assert "Available symbols:" in result

    def test_third_party_dep(self) -> None:
        """structlog.get_logger resolves (structlog is a project dependency)."""
        result = _src("structlog.get_logger")

        assert "def get_logger" in result

    def test_builtin_type(self) -> None:
        """builtins.dict is a C extension — no source available."""
        result = _src("builtins.dict")

        assert "Source not available" in result
        assert "built-in/C extension" in result
