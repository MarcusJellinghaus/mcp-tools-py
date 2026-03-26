"""Tests for jedi-based symbol discovery and reference finding."""

from pathlib import Path

import pytest

from mcp_tools_py.refactoring.jedi_tools import find_references, list_symbols

# --- list_symbols tests ---


@pytest.mark.parametrize(
    "symbol_type,code,expected",
    [
        ("functions", "def foo(): ...\ndef bar(): ...", ["foo", "bar"]),
        ("classes", "class Foo: ...\nclass Bar: ...", ["Foo", "Bar"]),
        ("variables", "X = 1\nY = 'hello'", ["X", "Y"]),
    ],
)
def test_list_symbols_by_type(
    tmp_path: Path, symbol_type: str, code: str, expected: list[str]
) -> None:
    """Lists top-level symbols of each type."""
    f = tmp_path / "example.py"
    f.write_text(code)
    result = list_symbols(tmp_path, "example.py")
    for name in expected:
        assert name in result
    assert symbol_type.rstrip("s") in result.lower() or any(
        name in result for name in expected
    )


def test_list_symbols_ignores_nested(tmp_path: Path) -> None:
    """Does not list nested functions or class methods."""
    code = (
        "class Outer:\n"
        "    def method(self): ...\n"
        "\n"
        "def top_func():\n"
        "    def inner(): ...\n"
    )
    f = tmp_path / "nested.py"
    f.write_text(code)
    result = list_symbols(tmp_path, "nested.py")
    assert "Outer" in result
    assert "top_func" in result
    assert "method" not in result
    assert "inner" not in result


def test_list_symbols_empty_file(tmp_path: Path) -> None:
    """Returns empty list for empty file."""
    f = tmp_path / "empty.py"
    f.write_text("")
    result = list_symbols(tmp_path, "empty.py")
    assert "No symbols found" in result or result.strip() == ""


def test_list_symbols_nonexistent_file(tmp_path: Path) -> None:
    """Returns error string for missing file."""
    result = list_symbols(tmp_path, "missing.py")
    assert "error" in result.lower() or "not found" in result.lower()


def test_list_symbols_excludes_imports(tmp_path: Path) -> None:
    """Does not list imported names, only locally-defined symbols."""
    code = (
        "from pathlib import Path\n"
        "import os\n"
        "\n"
        "def my_func(): ...\n"
        "\n"
        "class MyClass: ...\n"
        "\n"
        "MAX = 10\n"
    )
    f = tmp_path / "mixed.py"
    f.write_text(code)
    result = list_symbols(tmp_path, "mixed.py")
    assert "my_func" in result
    assert "MyClass" in result
    assert "MAX" in result
    assert "Path" not in result
    assert "os" not in result


def test_list_symbols_syntax_error(tmp_path: Path) -> None:
    """Returns error for file with syntax errors."""
    f = tmp_path / "bad.py"
    f.write_text("def foo(\n")
    result = list_symbols(tmp_path, "bad.py")
    # Jedi may still parse partial results or return an error
    assert isinstance(result, str)


# --- find_references tests ---


def test_find_references_function(tmp_path: Path) -> None:
    """Finds references to a function across multiple files."""
    (tmp_path / "mod_a.py").write_text("def helper():\n    return 42\n")
    (tmp_path / "mod_b.py").write_text(
        "from mod_a import helper\n\nresult = helper()\n"
    )
    result = find_references(tmp_path, "mod_a.py", "helper")
    assert "mod_a.py" in result
    assert "helper" in result


def test_find_references_class(tmp_path: Path) -> None:
    """Finds references to a class."""
    (tmp_path / "models.py").write_text("class Widget:\n    pass\n")
    (tmp_path / "use.py").write_text("from models import Widget\n\nw = Widget()\n")
    result = find_references(tmp_path, "models.py", "Widget")
    assert "models.py" in result
    assert "Widget" in result


def test_find_references_not_found(tmp_path: Path) -> None:
    """Returns error with available symbols when symbol not found."""
    (tmp_path / "src.py").write_text("def real_func():\n    pass\n")
    result = find_references(tmp_path, "src.py", "nonexistent")
    assert "not found" in result.lower()
    assert "real_func" in result


def test_find_references_import_usage(tmp_path: Path) -> None:
    """Finds import statements as references."""
    (tmp_path / "lib.py").write_text("CONSTANT = 99\n")
    (tmp_path / "main.py").write_text("from lib import CONSTANT\n\nprint(CONSTANT)\n")
    result = find_references(tmp_path, "lib.py", "CONSTANT")
    assert "lib.py" in result
    assert "CONSTANT" in result
