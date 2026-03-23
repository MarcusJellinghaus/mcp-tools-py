"""Tests for rope-based refactoring operations (move, rename)."""

from pathlib import Path

import pytest

from mcp_tools_py.refactoring.rope_tools import move_module, move_symbol, rename_symbol

# --- Shared fixture ---


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python project with 2 modules."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "foo.py").write_text(
        "def my_func():\n"
        "    return 42\n"
        "\n"
        "\n"
        "class MyClass:\n"
        "    pass\n"
        "\n"
        "\n"
        'MY_VAR = "hello"\n'
    )
    (src / "bar.py").write_text(
        "from src.foo import my_func\n"
        "\n"
        "\n"
        "def use_it():\n"
        "    return my_func()\n"
    )
    return tmp_path


# --- move_symbol tests ---


@pytest.mark.parametrize(
    "symbol_name",
    ["my_func", "MyClass", "MY_VAR"],
    ids=["function", "class", "variable"],
)
def test_move_symbol(sample_project: Path, symbol_name: str) -> None:
    """Move various symbol types to another module."""
    result = move_symbol(sample_project, "src/foo.py", symbol_name, "src/baz.py")
    assert "modified" in result.lower() or "created" in result.lower()
    baz = sample_project / "src" / "baz.py"
    assert baz.exists()
    assert symbol_name in baz.read_text()
    # Symbol should be removed from source
    foo_text = (sample_project / "src" / "foo.py").read_text()
    # For functions/classes the def/class line should be gone
    if symbol_name == "my_func":
        assert "def my_func" not in foo_text
    elif symbol_name == "MyClass":
        assert "class MyClass" not in foo_text


def test_move_symbol_updates_imports(sample_project: Path) -> None:
    """Move a function and verify imports are updated in consumers."""
    move_symbol(sample_project, "src/foo.py", "my_func", "src/baz.py")
    bar_text = (sample_project / "src" / "bar.py").read_text()
    assert "my_func" in bar_text
    # Import should now reference baz, not foo
    assert "baz" in bar_text


def test_move_symbol_dry_run(sample_project: Path) -> None:
    """Dry run reports changes without applying them."""
    result = move_symbol(
        sample_project, "src/foo.py", "my_func", "src/baz.py", dry_run=True
    )
    assert "[DRY RUN]" in result
    # foo.py should be unchanged
    foo_text = (sample_project / "src" / "foo.py").read_text()
    assert "def my_func" in foo_text
    assert not (sample_project / "src" / "baz.py").exists()


def test_move_symbol_creates_dest_file(sample_project: Path) -> None:
    """Auto-creates destination file if it doesn't exist."""
    move_symbol(sample_project, "src/foo.py", "my_func", "src/new_module.py")
    assert (sample_project / "src" / "new_module.py").exists()


def test_move_symbol_creates_init_files(sample_project: Path) -> None:
    """Auto-creates __init__.py files for new packages."""
    move_symbol(sample_project, "src/foo.py", "my_func", "src/sub/new_module.py")
    assert (sample_project / "src" / "sub" / "__init__.py").exists()
    assert (sample_project / "src" / "sub" / "new_module.py").exists()


def test_move_symbol_not_found(sample_project: Path) -> None:
    """Error with available symbols when symbol not found."""
    result = move_symbol(sample_project, "src/foo.py", "nonexistent", "src/baz.py")
    assert "not found" in result.lower()
    assert "my_func" in result


def test_move_symbol_name_collision(sample_project: Path) -> None:
    """Error when destination already defines same symbol name."""
    (sample_project / "src" / "baz.py").write_text("def my_func(): pass\n")
    result = move_symbol(sample_project, "src/foo.py", "my_func", "src/baz.py")
    assert "collision" in result.lower() or "already" in result.lower()


# --- rename_symbol tests ---


@pytest.mark.parametrize(
    "symbol_name,new_name",
    [
        ("my_func", "better_name"),
        ("MyClass", "BetterClass"),
        ("MY_VAR", "BETTER_VAR"),
    ],
    ids=["function", "class", "variable"],
)
def test_rename_symbol(sample_project: Path, symbol_name: str, new_name: str) -> None:
    """Rename various symbol types and verify references updated."""
    result = rename_symbol(sample_project, "src/foo.py", symbol_name, new_name)
    assert "modified" in result.lower()
    foo_text = (sample_project / "src" / "foo.py").read_text()
    assert new_name in foo_text
    assert symbol_name not in foo_text


def test_rename_updates_references(sample_project: Path) -> None:
    """Rename a function and verify all references are updated."""
    rename_symbol(sample_project, "src/foo.py", "my_func", "better_name")
    bar_text = (sample_project / "src" / "bar.py").read_text()
    assert "better_name" in bar_text
    assert "my_func" not in bar_text


def test_rename_dry_run(sample_project: Path) -> None:
    """Dry run reports changes without applying."""
    result = rename_symbol(
        sample_project, "src/foo.py", "my_func", "better_name", dry_run=True
    )
    assert "[DRY RUN]" in result
    foo_text = (sample_project / "src" / "foo.py").read_text()
    assert "def my_func" in foo_text


def test_rename_not_found(sample_project: Path) -> None:
    """Error with available symbols when symbol not found."""
    result = rename_symbol(sample_project, "src/foo.py", "nonexistent", "new_name")
    assert "not found" in result.lower()


# --- move_module tests ---


def test_move_module(sample_project: Path) -> None:
    """Move a module to a new package, verify imports updated."""
    (sample_project / "src" / "subpkg").mkdir()
    (sample_project / "src" / "subpkg" / "__init__.py").write_text("")
    result = move_module(sample_project, "src/foo.py", "src/subpkg")
    assert "modified" in result.lower()
    assert (sample_project / "src" / "subpkg" / "foo.py").exists()
    bar_text = (sample_project / "src" / "bar.py").read_text()
    assert "subpkg" in bar_text


def test_move_module_dry_run(sample_project: Path) -> None:
    """Dry run reports changes without applying."""
    (sample_project / "src" / "subpkg").mkdir()
    (sample_project / "src" / "subpkg" / "__init__.py").write_text("")
    result = move_module(sample_project, "src/foo.py", "src/subpkg", dry_run=True)
    assert "[DRY RUN]" in result
    # foo.py should still be in original location
    assert (sample_project / "src" / "foo.py").exists()
