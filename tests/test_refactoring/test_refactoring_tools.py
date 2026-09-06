"""Tests for RefactoringTools registration and relative-path output."""

import sys
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import pytest

from mcp_tools_py.refactoring import RefactoringTools
from mcp_tools_py.refactoring.jedi_tools import _get_project
from mcp_tools_py.utils.python_environment import PythonEnvironment

TEST_ENV = PythonEnvironment(Path(sys.executable))


@pytest.fixture(autouse=True)
def _clear_project_cache() -> Iterator[None]:
    """Drop cached jedi projects so their child processes are released."""
    _get_project.cache_clear()
    yield
    _get_project.cache_clear()


@pytest.fixture
def mock_mcp() -> MagicMock:
    """Create a mock FastMCP that captures tool registrations."""
    mcp = MagicMock()
    registered_functions: list[object] = []

    def tool_decorator() -> object:
        def decorator(fn: object) -> object:
            registered_functions.append(fn)
            return fn

        return decorator

    mcp.tool.side_effect = tool_decorator
    mcp._registered_functions = registered_functions
    return mcp


# --- Registration tests ---


def test_refactoring_tools_registers_five_tools(
    tmp_path: Path, mock_mcp: MagicMock
) -> None:
    """RefactoringTools registers all 5 tools on an MCP server."""
    tools = RefactoringTools(tmp_path, TEST_ENV)
    tools.register(mock_mcp)

    assert mock_mcp.tool.call_count == 5


def test_refactoring_tools_registers_expected_names(
    tmp_path: Path, mock_mcp: MagicMock
) -> None:
    """RefactoringTools registers tools with the correct function names."""
    tools = RefactoringTools(tmp_path, TEST_ENV)
    tools.register(mock_mcp)

    registered = mock_mcp._registered_functions
    names = {fn.__name__ for fn in registered}
    expected = {
        "list_symbols",
        "find_references",
        "move_symbol",
        "rename_symbol",
        "move_module",
    }
    assert names == expected


# --- Relative-path tests ---


def test_list_symbols_output_uses_relative_paths(tmp_path: Path) -> None:
    """list_symbols output contains relative paths, never absolute."""
    src = tmp_path / "example.py"
    src.write_text("def greet():\n    pass\n\nclass User:\n    pass\n")

    from mcp_tools_py.refactoring.jedi_tools import list_symbols

    result = list_symbols(tmp_path, "example.py", sys.executable)

    assert str(tmp_path) not in result
    assert "example.py" in result
    assert "greet" in result
    assert "User" in result


def test_find_references_output_uses_relative_paths(tmp_path: Path) -> None:
    """find_references output contains relative paths, never absolute."""
    (tmp_path / "models.py").write_text("class Item:\n    pass\n")
    (tmp_path / "use.py").write_text("from models import Item\n\nx = Item()\n")

    from mcp_tools_py.refactoring.jedi_tools import find_references

    result = find_references(tmp_path, "models.py", "Item", sys.executable)

    assert str(tmp_path) not in result
    assert "models.py" in result
    assert "Item" in result


def test_registered_list_symbols_uses_relative_paths(
    tmp_path: Path, mock_mcp: MagicMock
) -> None:
    """list_symbols via registration produces relative paths."""
    src = tmp_path / "mod.py"
    src.write_text("X = 42\n")

    tools = RefactoringTools(tmp_path, TEST_ENV)
    tools.register(mock_mcp)

    # Find the registered list_symbols function
    registered = mock_mcp._registered_functions
    list_symbols_fn = next(fn for fn in registered if fn.__name__ == "list_symbols")

    result = list_symbols_fn(file="mod.py")

    assert str(tmp_path) not in result
    assert "mod.py" in result


def test_registered_find_references_uses_relative_paths(
    tmp_path: Path, mock_mcp: MagicMock
) -> None:
    """find_references via registration produces relative paths."""
    (tmp_path / "lib.py").write_text("VAL = 100\n")
    (tmp_path / "main.py").write_text("from lib import VAL\nprint(VAL)\n")

    tools = RefactoringTools(tmp_path, TEST_ENV)
    tools.register(mock_mcp)

    registered = mock_mcp._registered_functions
    find_refs_fn = next(fn for fn in registered if fn.__name__ == "find_references")

    result = find_refs_fn(file="lib.py", symbol_name="VAL")

    assert str(tmp_path) not in result
    assert "lib.py" in result
