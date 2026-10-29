"""Tests for rope-based refactoring operations (move, rename)."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from mcp_tools_py.refactoring.rope_tools import (
    _build_ignored_resources,
    move_module,
    move_symbol,
    rename_symbol,
)
from mcp_tools_py.utils.subprocess_runner import CommandResult

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
    result = move_symbol(sample_project, "src/foo.py", [symbol_name], "src/baz.py")
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
    move_symbol(sample_project, "src/foo.py", ["my_func"], "src/baz.py")
    bar_text = (sample_project / "src" / "bar.py").read_text()
    assert "my_func" in bar_text
    # Import should now reference baz, not foo
    assert "baz" in bar_text


def test_move_symbol_dry_run(sample_project: Path) -> None:
    """Dry run reports changes without applying them."""
    result = move_symbol(
        sample_project, "src/foo.py", ["my_func"], "src/baz.py", dry_run=True
    )
    assert "[DRY RUN]" in result
    # foo.py should be unchanged
    foo_text = (sample_project / "src" / "foo.py").read_text()
    assert "def my_func" in foo_text
    assert not (sample_project / "src" / "baz.py").exists()


def test_move_symbol_creates_dest_file(sample_project: Path) -> None:
    """Auto-creates destination file if it doesn't exist."""
    move_symbol(sample_project, "src/foo.py", ["my_func"], "src/new_module.py")
    assert (sample_project / "src" / "new_module.py").exists()


def test_move_symbol_creates_init_files(sample_project: Path) -> None:
    """Auto-creates __init__.py files for new packages."""
    move_symbol(sample_project, "src/foo.py", ["my_func"], "src/sub/new_module.py")
    assert (sample_project / "src" / "sub" / "__init__.py").exists()
    assert (sample_project / "src" / "sub" / "new_module.py").exists()


def test_move_symbol_not_found(sample_project: Path) -> None:
    """Error with available symbols when symbol not found."""
    result = move_symbol(sample_project, "src/foo.py", ["nonexistent"], "src/baz.py")
    assert "not found" in result.lower()
    assert "my_func" in result


def test_move_symbol_name_collision(sample_project: Path) -> None:
    """Error when destination already defines same symbol name."""
    (sample_project / "src" / "baz.py").write_text("def my_func(): pass\n")
    result = move_symbol(sample_project, "src/foo.py", ["my_func"], "src/baz.py")
    assert "collision" in result.lower() or "already" in result.lower()


def test_move_symbol_uses_from_import_style(sample_project: Path) -> None:
    """move_symbol should produce 'from ... import' style, not 'import ...' style."""
    move_symbol(sample_project, "src/foo.py", ["my_func"], "src/baz.py")
    bar_text = (sample_project / "src" / "bar.py").read_text()
    # prefer_module_from_imports=True makes rope use "from pkg import mod" style
    # instead of "import pkg.mod" with fully-qualified usage
    assert (
        "from src import baz" in bar_text or "from src.baz import my_func" in bar_text
    )
    # Should NOT use "import src.baz" fully-qualified style
    assert "import src.baz\n" not in bar_text


# --- batch move_symbol tests ---


def test_move_symbol_batch(sample_project: Path) -> None:
    """Move multiple symbols in one call, verify all arrive in destination."""
    result = move_symbol(
        sample_project, "src/foo.py", ["my_func", "MyClass"], "src/baz.py"
    )
    assert "successfully" in result.lower()
    baz_text = (sample_project / "src" / "baz.py").read_text()
    assert "my_func" in baz_text
    assert "MyClass" in baz_text
    foo_text = (sample_project / "src" / "foo.py").read_text()
    assert "def my_func" not in foo_text
    assert "class MyClass" not in foo_text


def test_move_symbol_batch_ordering(sample_project: Path) -> None:
    """Batch move preserves symbol order in destination file."""
    result = move_symbol(
        sample_project,
        "src/foo.py",
        ["my_func", "MyClass", "MY_VAR"],
        "src/baz.py",
    )
    assert "successfully" in result.lower()
    baz_text = (sample_project / "src" / "baz.py").read_text()
    # Symbols should appear in the order they were listed
    pos_func = baz_text.index("my_func")
    pos_class = baz_text.index("MyClass")
    pos_var = baz_text.index("MY_VAR")
    assert pos_func < pos_class < pos_var


def test_move_symbol_batch_validation_all_or_nothing(sample_project: Path) -> None:
    """If any symbol fails validation, no symbols are moved."""
    result = move_symbol(
        sample_project,
        "src/foo.py",
        ["my_func", "nonexistent"],
        "src/baz.py",
    )
    assert "not found" in result.lower()
    # No symbols should have been moved
    foo_text = (sample_project / "src" / "foo.py").read_text()
    assert "def my_func" in foo_text
    assert not (sample_project / "src" / "baz.py").exists()


def test_move_symbol_batch_collision_check(sample_project: Path) -> None:
    """If any symbol collides with destination, entire batch fails."""
    (sample_project / "src" / "baz.py").write_text("class MyClass: pass\n")
    result = move_symbol(
        sample_project,
        "src/foo.py",
        ["my_func", "MyClass"],
        "src/baz.py",
    )
    assert "collision" in result.lower() or "already" in result.lower()
    # No symbols should have been moved
    foo_text = (sample_project / "src" / "foo.py").read_text()
    assert "def my_func" in foo_text


def test_move_symbol_batch_duplicate_names(sample_project: Path) -> None:
    """Duplicate symbol names in the list are rejected."""
    result = move_symbol(
        sample_project,
        "src/foo.py",
        ["my_func", "my_func"],
        "src/baz.py",
    )
    assert "duplicate" in result.lower()


# --- result output tests ---


def test_move_symbol_result_includes_review_notes(sample_project: Path) -> None:
    """Result output includes import style note and review reminder."""
    result = move_symbol(
        sample_project, "src/foo.py", ["my_func", "MyClass"], "src/baz.py"
    )
    assert "successfully" in result
    assert "Moved: my_func, MyClass (from src/foo.py" in result
    assert "src/baz.py" in result
    assert "Note: Imports are absolute" in result
    assert "Note: Review symbol order and imports in all affected files." in result


def test_move_symbol_dry_run_includes_review_notes(sample_project: Path) -> None:
    """Dry-run output includes symbols line and review reminder notes."""
    result = move_symbol(
        sample_project,
        "src/foo.py",
        ["my_func", "MyClass"],
        "src/baz.py",
        dry_run=True,
    )
    assert "[DRY RUN] move_symbol preview:" in result
    assert "Symbols: my_func, MyClass" in result
    assert "Note: Imports are absolute" in result
    assert "Note: Review symbol order and imports in all affected files." in result


def test_move_symbol_dry_run_shows_diff(sample_project: Path) -> None:
    """Dry-run output includes rope's unified diff for each symbol."""
    result = move_symbol(
        sample_project, "src/foo.py", ["my_func"], "src/baz.py", dry_run=True
    )
    assert "Diff for my_func:" in result
    assert "--- a/src/foo.py" in result
    assert "+++ b/src/baz.py" in result
    assert "-def my_func():" in result
    assert "Self-referencing imports" in result
    assert not (sample_project / "src" / "baz.py").exists()


# --- self-import removal tests ---


def test_move_symbol_removes_self_import(tmp_path: Path) -> None:
    """After moving a symbol, self-referencing imports are removed from destination."""
    # Create a project where rope will generate a self-import.
    # This happens when module A imports from module B, and we move a symbol
    # from B to A — rope adds "from A import ..." inside A itself.
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "source.py").write_text(
        "from pkg.dest import helper\n"
        "\n"
        "\n"
        "def mover():\n"
        "    return helper()\n"
    )
    (pkg / "dest.py").write_text(
        "def helper():\n"
        "    return 1\n"
        "\n"
        "\n"
        "def stay_here():\n"
        "    return 2\n"
    )
    result = move_symbol(tmp_path, "pkg/source.py", ["mover"], "pkg/dest.py")
    assert "successfully" in result.lower()
    dest_text = (tmp_path / "pkg" / "dest.py").read_text()
    # The destination should NOT contain a self-referencing import
    assert "from pkg.dest import" not in dest_text
    assert "import pkg.dest" not in dest_text
    # The moved symbol should be present
    assert "def mover" in dest_text
    # helper should still be defined
    assert "def helper" in dest_text


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


# --- AttributeError hint hardening tests ---


def test_move_module_attribute_error_hint(sample_project: Path) -> None:
    """When rope raises AttributeError, original text + actionable hint appear."""
    from unittest.mock import patch

    from mcp_tools_py.refactoring.rope_tools import _move_module_impl

    with patch(
        "rope.refactor.move.create_move",
        side_effect=AttributeError("'NoneType' object has no attribute 'is_folder'"),
    ):
        result = _move_module_impl(
            sample_project, "src/foo.py", "src/pkg", dry_run=True
        )
    # Original error text preserved for debugging
    assert "is_folder" in result
    # Actionable hint appended
    assert "Hint:" in result
    assert "move the file manually" in result
    # The temp dest package created for the dry run was cleaned up
    assert not (sample_project / "src" / "pkg").exists()


def test_move_symbol_attribute_error_hint(sample_project: Path) -> None:
    """When rope raises AttributeError, original text + actionable hint appear."""
    from unittest.mock import patch

    from mcp_tools_py.refactoring.rope_tools import _move_symbol_impl

    with patch(
        "rope.refactor.move.create_move",
        side_effect=AttributeError("'NoneType' object has no attribute 'is_folder'"),
    ):
        result = _move_symbol_impl(
            sample_project, "src/foo.py", ["my_func"], "src/baz.py", dry_run=True
        )
    # Original error text preserved for debugging
    assert "Error moving symbol:" in result
    assert "is_folder" in result
    # Actionable hint appended
    assert "Hint:" in result


# --- parent-side cleanup tests ---


def fake_execute_command(
    side_effect: Callable[[], None],
    result: CommandResult | None = None,
) -> Callable[..., CommandResult]:
    """Build a fake execute_command that runs side_effect, then returns result.

    Returns:
        A replacement for rope_tools.execute_command; defaults to a timeout.
    """
    if result is None:
        result = CommandResult(return_code=-1, stdout="", stderr="", timed_out=True)

    def _fake(*_args: object, **_kwargs: object) -> CommandResult:
        side_effect()
        return result

    return _fake


def test_move_symbol_dry_run_timeout_leaves_no_files(
    sample_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dry run whose child is killed still removes what the child created."""
    sub = sample_project / "src" / "sub"

    def create_files() -> None:
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "new.py").write_text("")

    monkeypatch.setattr(
        "mcp_tools_py.refactoring.rope_tools.execute_command",
        fake_execute_command(create_files),
    )
    result = move_symbol(
        sample_project, "src/foo.py", ["my_func"], "src/sub/new.py", dry_run=True
    )
    assert "timed out" in result
    assert not sub.exists()


def test_move_symbol_dry_run_existing_dir_no_stray_init(sample_project: Path) -> None:
    """A dry run into an existing non-package dir leaves no __init__.py behind."""
    plain = sample_project / "src" / "plain"
    plain.mkdir()
    (plain / "other.txt").write_text("keep")
    result = move_symbol(
        sample_project, "src/foo.py", ["my_func"], "src/plain/new.py", dry_run=True
    )
    assert "[DRY RUN]" in result
    assert not (plain / "__init__.py").exists()
    assert not (plain / "new.py").exists()
    assert (plain / "other.txt").exists()


def test_move_symbol_real_timeout_lists_moved(
    sample_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real run killed mid-batch reports which symbols moved."""
    src = sample_project / "src"

    def move_one() -> None:
        (src / "foo.py").write_text('class MyClass:\n    pass\n\n\nMY_VAR = "hello"\n')
        (src / "baz.py").write_text("def my_func(): ...\n")

    monkeypatch.setattr(
        "mcp_tools_py.refactoring.rope_tools.execute_command",
        fake_execute_command(move_one),
    )
    result = move_symbol(
        sample_project, "src/foo.py", ["my_func", "MyClass"], "src/baz.py"
    )
    assert "timed out" in result
    assert "Moved: my_func" in result
    assert "Not moved: MyClass" in result
    assert "git diff" in result
    assert (src / "baz.py").exists()


def _create_sub_package(sub: Path) -> Callable[[], None]:
    """Build a side effect that creates sub/__init__.py and sub/new.py.

    Returns:
        A callable for fake_execute_command.
    """

    def create_files() -> None:
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        (sub / "new.py").write_text("")

    return create_files


def test_move_symbol_real_failure_nothing_moved_cleans_up(
    sample_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real run that times out before moving anything leaves no files."""
    sub = sample_project / "src" / "sub"
    monkeypatch.setattr(
        "mcp_tools_py.refactoring.rope_tools.execute_command",
        fake_execute_command(_create_sub_package(sub)),
    )
    result = move_symbol(sample_project, "src/foo.py", ["my_func"], "src/sub/new.py")
    assert not sub.exists()
    assert "Moved: (none)" in result


def test_move_symbol_real_rope_error_nothing_moved_cleans_up(
    sample_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rope error before anything moved is reported and cleaned up."""
    sub = sample_project / "src" / "sub"
    rope_error = CommandResult(
        return_code=0,
        stdout='{"result": "Error moving symbol: boom"}',
        stderr="",
        timed_out=False,
    )
    monkeypatch.setattr(
        "mcp_tools_py.refactoring.rope_tools.execute_command",
        fake_execute_command(_create_sub_package(sub), rope_error),
    )
    result = move_symbol(sample_project, "src/foo.py", ["my_func"], "src/sub/new.py")
    assert "Error moving symbol: boom" in result
    assert "Moved: (none)" in result
    assert "Not moved: my_func" in result
    assert "git diff" in result
    assert not sub.exists()


# --- ropefolder=None and gitignore filtering tests ---


def test_rope_does_not_create_ropeproject_folder(sample_project: Path) -> None:
    """After rename_symbol, assert no .ropeproject/ directory exists."""
    rename_symbol(sample_project, "src/foo.py", "my_func", "better_name")
    assert not (sample_project / ".ropeproject").exists()


def test_build_ignored_resources_defaults_without_gitignore(tmp_path: Path) -> None:
    """Without .gitignore, returns hardcoded defaults."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")
    result = _build_ignored_resources(tmp_path)
    assert ".ropeproject" in result
    assert "__pycache__" in result
    assert ".git" in result
    assert "node_modules" in result


def test_build_ignored_resources_includes_gitignore_patterns(tmp_path: Path) -> None:
    """With .gitignore containing ignoreme/, the result includes ignoreme."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "ignoreme").mkdir()
    (tmp_path / ".gitignore").write_text("ignoreme/\n")
    result = _build_ignored_resources(tmp_path)
    assert "ignoreme" in result
    # Defaults should still be present
    assert ".ropeproject" in result
    assert "__pycache__" in result


def test_build_ignored_resources_no_backslashes(tmp_path: Path) -> None:
    """Patterns must use forward slashes — Rope compiles them as regex."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep").mkdir()
    (tmp_path / ".gitignore").write_text("sub/deep/\n")
    result = _build_ignored_resources(tmp_path)
    for pattern in result:
        assert "\\" not in pattern, f"Backslash in pattern: {pattern!r}"


def test_cli_parse_args_default_timeout() -> None:
    """parse_args returns refactoring_timeout=120 by default."""
    import sys
    from unittest.mock import patch

    from mcp_tools_py.main import parse_args

    with patch.object(sys, "argv", ["prog", "--project-dir", "/tmp/proj"]):
        args = parse_args()
    assert args.refactoring_timeout == 120


def test_cli_parse_args_custom_timeout() -> None:
    """parse_args accepts --refactoring-timeout 60."""
    import sys
    from unittest.mock import patch

    from mcp_tools_py.main import parse_args

    with patch.object(
        sys,
        "argv",
        ["prog", "--project-dir", "/tmp/proj", "--refactoring-timeout", "60"],
    ):
        args = parse_args()
    assert args.refactoring_timeout == 60


def test_rope_cli_returns_json_error_on_exception() -> None:
    """rope_cli returns structured JSON error, not raw traceback."""
    import subprocess
    import sys

    # Pass valid operation but missing required args to trigger KeyError
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mcp_tools_py.refactoring.rope_cli",
            "rename_symbol",
            '{"project_dir": "/nonexistent"}',
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    output = json.loads(proc.stdout)
    assert "error" in output


def test_rope_cli_unknown_operation() -> None:
    """rope_cli exits 1 on unknown operation."""
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mcp_tools_py.refactoring.rope_cli",
            "unknown_op",
            "{}",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "Unknown operation" in proc.stderr


def test_refactoring_tools_init_stores_timeout(tmp_path: Path) -> None:
    """RefactoringTools(context, timeout=60)._timeout == 60."""
    import sys

    from mcp_tools_py.refactoring import RefactoringTools
    from mcp_tools_py.utils.python_environment import PythonEnvironment
    from mcp_tools_py.utils.tool_context import ToolContext

    context = ToolContext(
        project_dir=tmp_path,
        environment=PythonEnvironment(Path(sys.executable)),
    )
    tools = RefactoringTools(context, timeout=60)
    assert tools._timeout == 60  # noqa: SLF001
