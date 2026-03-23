# Step 3: Rope Tools — move_symbol, rename, move_module

**Commit:** `feat: add move_symbol, rename, and move_module tools (#108)`

**Context:** See `pr_info/steps/summary.md` for full issue context. Steps 1-2 must be completed first.

**Goal:** Implement the three rope-based refactoring tools, register them via `RefactoringTools`, and add tests. These tools modify files and support dry-run mode.

---

## LLM Prompt

> **Task:** Implement Step 3 of Issue #108 (Add Python refactoring tools).
> Read `pr_info/steps/summary.md` for full context, then follow `pr_info/steps/step_3.md` exactly.
>
> Implement `move_symbol`, `rename_symbol`, and `move_module` in `rope_tools.py`.
> Register all three via `RefactoringTools` in `refactoring/__init__.py`.
> Write tests first (TDD). All checks must pass.

---

## Part A: Tests for rope tools

### WHERE
- `tests/test_refactoring/test_rope_tools.py` (new)

### WHAT
```python
import pytest
from pathlib import Path

from mcp_tools_py.refactoring.rope_tools import move_symbol, rename_symbol, move_module

# --- Shared fixture ---

@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python project with 2 modules."""
    # src/foo.py: defines my_func, MyClass, MY_VAR
    # src/bar.py: imports and uses my_func from foo
    # src/__init__.py: empty
    ...
    return tmp_path

# --- move_symbol tests ---

def test_move_symbol_function(sample_project: Path) -> None:
    """Move a function to another module, verify imports updated."""
    result = move_symbol(sample_project, "src/foo.py", "my_func", "src/baz.py")
    assert "Modified:" in result or "Created:" in result
    # Verify foo.py no longer defines my_func
    # Verify baz.py defines my_func
    # Verify bar.py imports from baz, not foo

def test_move_symbol_dry_run(sample_project: Path) -> None:
    """Dry run reports changes without applying them."""
    result = move_symbol(sample_project, "src/foo.py", "my_func", "src/baz.py", dry_run=True)
    assert "[DRY RUN]" in result
    # Verify foo.py still defines my_func (unchanged)

def test_move_symbol_creates_dest_file(sample_project: Path) -> None:
    """Auto-creates destination file if it doesn't exist."""
    result = move_symbol(sample_project, "src/foo.py", "my_func", "src/new_module.py")
    assert (sample_project / "src" / "new_module.py").exists()

def test_move_symbol_creates_init_files(sample_project: Path) -> None:
    """Auto-creates __init__.py files for new packages."""
    result = move_symbol(sample_project, "src/foo.py", "my_func", "src/sub/new_module.py")
    assert (sample_project / "src" / "sub" / "__init__.py").exists()

def test_move_symbol_not_found(sample_project: Path) -> None:
    """Error with available symbols when symbol not found."""
    result = move_symbol(sample_project, "src/foo.py", "nonexistent", "src/baz.py")
    assert "not found" in result.lower()
    assert "my_func" in result  # hint: available symbols

def test_move_symbol_name_collision(sample_project: Path) -> None:
    """Error when destination already defines same symbol name."""
    # bar.py already has something; create collision scenario
    ...

# --- rename_symbol tests ---

def test_rename_function(sample_project: Path) -> None:
    """Rename a function, verify all references updated."""
    result = rename_symbol(sample_project, "src/foo.py", "my_func", "better_name")
    assert "Modified:" in result
    # Verify foo.py defines better_name, not my_func
    # Verify bar.py imports better_name

def test_rename_dry_run(sample_project: Path) -> None:
    """Dry run reports changes without applying."""
    result = rename_symbol(sample_project, "src/foo.py", "my_func", "better_name", dry_run=True)
    assert "[DRY RUN]" in result

def test_rename_not_found(sample_project: Path) -> None:
    """Error with available symbols when symbol not found."""
    result = rename_symbol(sample_project, "src/foo.py", "nonexistent", "new_name")
    assert "not found" in result.lower()

# --- move_module tests ---

def test_move_module(sample_project: Path) -> None:
    """Move a module to a new package, verify imports updated."""
    result = move_module(sample_project, "src/foo.py", "src/subpkg")
    assert "Modified:" in result
    # Verify src/subpkg/foo.py exists
    # Verify bar.py imports from subpkg.foo

def test_move_module_dry_run(sample_project: Path) -> None:
    """Dry run reports changes without applying."""
    result = move_module(sample_project, "src/foo.py", "src/subpkg", dry_run=True)
    assert "[DRY RUN]" in result
```

---

## Part B: Implement rope_tools.py

### WHERE
- `src/mcp_tools_py/refactoring/rope_tools.py`

### WHAT
```python
"""Rope-based refactoring operations (move, rename)."""

from pathlib import Path
from typing import Optional

def move_symbol(
    project_dir: Path,
    source_file: str,
    symbol_name: str,
    dest_file: str,
    dry_run: bool = False,
) -> str:
    """Move a top-level symbol to another module. Updates imports project-wide."""
    ...

def rename_symbol(
    project_dir: Path,
    file_path: str,
    symbol_name: str,
    new_name: str,
    dry_run: bool = False,
) -> str:
    """Rename a symbol and update all references project-wide."""
    ...

def move_module(
    project_dir: Path,
    source_module: str,
    dest_package: str,
    dry_run: bool = False,
) -> str:
    """Move an entire module to a new package. Updates all references."""
    ...
```

### ALGORITHM — shared helper `_with_rope_project`
```python
def _with_rope_project(project_dir: Path):
    """Context manager: open fresh rope Project, yield, close."""
    project = rope.base.project.Project(str(project_dir))
    try:
        yield project
    finally:
        project.close()
```

### ALGORITHM — move_symbol
```
1. Ensure dest_file parent dirs and __init__.py files exist (if not dry_run, create them; if dry_run, note them)
2. If dest_file doesn't exist and not dry_run, create empty file
3. Open rope Project via _with_rope_project
4. Get source Resource: project.root.get_child(source_file)
5. Find symbol offset using rope's pyobjects: parse source, iterate top-level names, match symbol_name
6. If not found: return error listing available top-level symbols
7. If dest already defines symbol_name: return name collision error
8. Create MoveGlobal mover: rope.refactor.move.create_move(project, source_resource, offset)
9. changes = mover.get_changes(dest_resource)
10. If dry_run: return formatted "[DRY RUN] Would modify: ..." from changes
11. project.do(changes) — apply
12. Return formatted "Modified: ..." / "Created: ..." change report
```

### ALGORITHM — rename_symbol
```
1. Open rope Project
2. Get source Resource, find symbol offset (same as move_symbol)
3. If not found: return error listing available symbols
4. Create Rename: rope.refactor.rename.Rename(project, source_resource, offset)
5. changes = renamer.get_changes(new_name)
6. If dry_run: return "[DRY RUN]" report
7. project.do(changes)
8. Return change report
```

### ALGORITHM — move_module
```
1. Open rope Project
2. Get source module Resource
3. Get/create dest package Resource
4. Create MoveModule: rope.refactor.move.create_move(project, source_resource)
5. changes = mover.get_changes(dest_resource)
6. If dry_run: return "[DRY RUN]" report
7. project.do(changes)
8. Return change report
```

### ALGORITHM — _format_changes (shared)
```python
def _format_changes(changes, project_dir: Path, dry_run: bool) -> str:
    prefix = "[DRY RUN] Would modify" if dry_run else "Modified"
    lines = []
    for change in changes.changes:
        rel_path = Path(change.resource.path)  # rope gives project-relative paths
        lines.append(f"  {prefix}: {rel_path}")
    return "\n".join(lines)
```

### DATA — change report format (apply mode)
```
move_symbol completed successfully.
  Modified: src/foo.py
  Modified: src/bar.py
  Created: src/baz.py
```

### DATA — change report format (dry-run mode)
```
[DRY RUN] move_symbol preview:
  Would modify: src/foo.py
  Would modify: src/bar.py
  Would create: src/baz.py
```

### DATA — error format (symbol not found)
```
Symbol 'nonexistent' not found in src/foo.py.
Available top-level symbols: my_func, MyClass, MY_VAR
```

---

## Part C: Register in RefactoringTools

### WHERE
- `src/mcp_tools_py/refactoring/__init__.py` (modify)

### WHAT — add to `register()` method
```python
from mcp_tools_py.refactoring.rope_tools import (
    move_symbol as rope_move_symbol,
    rename_symbol as rope_rename_symbol,
    move_module as rope_move_module,
)

# Inside register():

@mcp.tool()
@log_function_call
def move_symbol(
    source_file: str,
    symbol_name: str,
    dest_file: str,
    dry_run: bool = False,
) -> str:
    """Move a top-level function, class, or variable to another module.
    Updates all imports project-wide. Auto-creates destination file and
    missing __init__.py files if needed.

    Args:
        source_file: Source file path relative to project root.
        symbol_name: Name of the top-level symbol to move.
        dest_file: Destination file path relative to project root.
        dry_run: Preview changes without applying (default: False).
    """
    return rope_move_symbol(project_dir, source_file, symbol_name, dest_file, dry_run)

@mcp.tool()
@log_function_call
def rename(
    file: str,
    symbol_name: str,
    new_name: str,
    dry_run: bool = False,
) -> str:
    """Rename a module-level symbol and update all references project-wide.

    Args:
        file: File path relative to project root.
        symbol_name: Current name of the symbol.
        new_name: New name for the symbol.
        dry_run: Preview changes without applying (default: False).
    """
    return rope_rename_symbol(project_dir, file, symbol_name, new_name, dry_run)

@mcp.tool()
@log_function_call
def move_module(
    source_module: str,
    dest_package: str,
    dry_run: bool = False,
) -> str:
    """Move an entire module to a new package. Updates all references.

    Args:
        source_module: Source module path relative to project root.
        dest_package: Destination package path relative to project root.
        dry_run: Preview changes without applying (default: False).
    """
    return rope_move_module(project_dir, source_module, dest_package, dry_run)
```

---

## Verification Checklist

1. `test_rope_tools.py` tests pass
2. All existing tests + step 2 tests still pass
3. pylint, mypy pass on new code
4. Dry-run mode produces correct output format
5. Applied changes actually modify files correctly
