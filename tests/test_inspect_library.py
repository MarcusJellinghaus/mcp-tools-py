"""Unit tests for inspect_library module (mocked + real-import)."""

import types
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.inspect_library import _get_library_source


class TestParseImportPath:
    """Tests for import path resolution logic."""

    @patch("mcp_tools_py.inspect_library.inspect")
    @patch("mcp_tools_py.inspect_library.importlib")
    def test_parse_import_path_module_and_attr(
        self, mock_importlib: MagicMock, mock_inspect: MagicMock
    ) -> None:
        """'a.b.c.D' tries 'a.b.c.D' first, falls back to 'a.b.c' + getattr 'D'."""
        fake_module = types.ModuleType("a.b.c")
        fake_class = type("D", (), {})
        setattr(fake_module, "D", fake_class)

        # First call with "a.b.c.D" fails, second with "a.b.c" succeeds
        mock_importlib.import_module.side_effect = [ImportError, fake_module]
        mock_inspect.getsource.return_value = "class D:\n    pass\n"

        result = _get_library_source("a.b.c.D")

        assert "class D:" in result
        mock_inspect.getsource.assert_called_once_with(fake_class)

    @patch("mcp_tools_py.inspect_library.inspect")
    @patch("mcp_tools_py.inspect_library.importlib")
    def test_walk_backwards_resolution(
        self, mock_importlib: MagicMock, mock_inspect: MagicMock
    ) -> None:
        """Tries longest path first, falls back correctly."""
        fake_module = types.ModuleType("a")
        nested = MagicMock()
        nested.c = MagicMock()
        fake_module.b = nested  # type: ignore[attr-defined]

        # "a.b.c" fails, "a.b" fails, "a" succeeds
        mock_importlib.import_module.side_effect = [
            ImportError,
            ImportError,
            fake_module,
        ]
        mock_inspect.getsource.return_value = "def c():\n    pass\n"

        result = _get_library_source("a.b.c")

        assert "def c():" in result
        # Verify it tried longest path first
        calls = mock_importlib.import_module.call_args_list
        assert calls[0].args[0] == "a.b.c"
        assert calls[1].args[0] == "a.b"
        assert calls[2].args[0] == "a"


class TestTruncation:
    """Tests for source truncation logic."""

    @patch("mcp_tools_py.inspect_library.inspect")
    @patch("mcp_tools_py.inspect_library.importlib")
    def test_truncation_applied(
        self, mock_importlib: MagicMock, mock_inspect: MagicMock
    ) -> None:
        """Source > max_lines is truncated with correct message."""
        fake_module = types.ModuleType("mymod")
        mock_importlib.import_module.return_value = fake_module

        # 10 lines of source
        source_lines = [f"line {i}" for i in range(10)]
        mock_inspect.getsource.return_value = "\n".join(source_lines)

        result = _get_library_source("mymod", max_lines=3)

        assert "line 0" in result
        assert "line 1" in result
        assert "line 2" in result
        assert "line 9" not in result
        assert "... truncated (showing 3 of 10 lines)" in result
        assert "Use max_lines to see more." in result

    @patch("mcp_tools_py.inspect_library.inspect")
    @patch("mcp_tools_py.inspect_library.importlib")
    def test_truncation_not_applied(
        self, mock_importlib: MagicMock, mock_inspect: MagicMock
    ) -> None:
        """Source <= max_lines returns full source."""
        fake_module = types.ModuleType("mymod")
        mock_importlib.import_module.return_value = fake_module

        source = "def foo():\n    return 42\n"
        mock_inspect.getsource.return_value = source

        result = _get_library_source("mymod", max_lines=200)

        assert result == source
        assert "truncated" not in result


class TestErrorHandling:
    """Tests for error paths."""

    @patch("mcp_tools_py.inspect_library.importlib")
    def test_bad_module_error(self, mock_importlib: MagicMock) -> None:
        """All import attempts fail → clear error message."""
        mock_importlib.import_module.side_effect = ImportError

        result = _get_library_source("nonexistent.module.path")

        assert result == "Module 'nonexistent.module.path' not found"

    @patch("mcp_tools_py.inspect_library.inspect")
    @patch("mcp_tools_py.inspect_library.importlib")
    def test_bad_symbol_lists_available(
        self, mock_importlib: MagicMock, mock_inspect: MagicMock
    ) -> None:
        """Module found but attr missing → sorted list with types; verify 50-symbol cap."""
        fake_module = types.ModuleType("mymod")
        # Add 60 public attributes to test the 50-symbol cap
        for i in range(60):
            setattr(fake_module, f"symbol_{i:03d}", lambda: None)

        mock_importlib.import_module.side_effect = [ImportError, fake_module]
        mock_inspect.getmembers.return_value = [
            (name, getattr(fake_module, name))
            for name in sorted(dir(fake_module))
            if not name.startswith("_")
        ]

        result = _get_library_source("mymod.nonexistent")

        assert "'nonexistent' not found in module 'mymod'" in result
        assert "Available symbols:" in result
        # Verify cap at 50 symbols
        symbol_lines = [
            line for line in result.split("\n") if line.startswith("  symbol_")
        ]
        assert len(symbol_lines) == 50

    @patch("mcp_tools_py.inspect_library.inspect")
    @patch("mcp_tools_py.inspect_library.importlib")
    def test_builtin_c_extension_error(
        self, mock_importlib: MagicMock, mock_inspect: MagicMock
    ) -> None:
        """getsource raises TypeError → friendly message."""
        fake_module = types.ModuleType("mymod")
        mock_importlib.import_module.return_value = fake_module
        mock_inspect.getsource.side_effect = TypeError("built-in")

        result = _get_library_source("mymod")

        assert "Source not available for 'mymod' (built-in/C extension)" in result
        assert "Only pure-Python symbols have inspectable source." in result

    @pytest.mark.parametrize("bad_value", [0, -5, -1])
    def test_max_lines_invalid_returns_error(self, bad_value: int) -> None:
        """max_lines in [0, -5, -1] → validation error."""
        result = _get_library_source("anything", max_lines=bad_value)

        assert (
            f"max_lines must be a positive integer (>= 1), got: {bad_value}" == result
        )


class TestRealImports:
    """Real-import tests against actual installed packages (no mocking)."""

    def test_stdlib_class(self) -> None:
        """json.encoder.JSONEncoder resolves to the real class source."""
        result = _get_library_source("json.encoder.JSONEncoder")

        assert "def encode" in result

    def test_module_level(self) -> None:
        """json.encoder resolves to the full module source."""
        result = _get_library_source("json.encoder")

        assert "class JSONEncoder" in result

    def test_nested_attribute(self) -> None:
        """json.encoder.JSONEncoder.encode resolves to just the method."""
        method_source = _get_library_source("json.encoder.JSONEncoder.encode")
        class_source = _get_library_source("json.encoder.JSONEncoder")

        assert "def encode" in method_source
        assert len(method_source) < len(class_source)

    def test_custom_max_lines_truncation(self) -> None:
        """JSONEncoder source is truncated when max_lines=50."""
        result = _get_library_source("json.encoder.JSONEncoder", max_lines=50)

        assert "truncated" in result
        assert "showing 50 of" in result

    def test_bad_module(self) -> None:
        """Completely unknown package returns 'not found'."""
        result = _get_library_source("nonexistent_package.Foo")

        assert "not found" in result

    def test_bad_symbol_lists_available(self) -> None:
        """Known module + bad symbol lists available symbols with types."""
        result = _get_library_source("json.NoSuchThing")

        assert "not found in module" in result
        assert "Available symbols:" in result

    def test_third_party_dep(self) -> None:
        """structlog.get_logger resolves (structlog is a project dependency)."""
        result = _get_library_source("structlog.get_logger")

        assert "def get_logger" in result

    def test_builtin_type(self) -> None:
        """builtins.dict is a C extension — no source available."""
        result = _get_library_source("builtins.dict")

        assert "Source not available" in result
        assert "built-in/C extension" in result
