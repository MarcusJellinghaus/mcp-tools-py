# Step 3: Self-referencing import removal

> **Context**: See [summary.md](summary.md) for full issue overview.

## Goal

After moving symbols, detect and remove import lines in the destination file that
reference the destination module itself. These are always rope artifacts.

## WHERE

| File | Function/Section |
|------|-----------------|
| `src/mcp_tools_py/refactoring/rope_tools.py` | New helper `_remove_self_imports()`, called from `_move_symbol_impl()` |
| `tests/test_refactoring/test_rope_tools.py` | New test for self-import removal |

## WHAT

### New helper function

```python
def _remove_self_imports(dest_path: Path, dest_module_dotted: str) -> list[str]:
    """Remove import lines that reference the destination module itself.

    Args:
        dest_path: Absolute path to the destination file.
        dest_module_dotted: Dotted module name (e.g. "pkg.sub.module").

    Returns:
        List of removed import lines (for reporting).
    """
```

### Integration in `_move_symbol_impl()`

After all moves complete (after the loop from Step 2), call `_remove_self_imports()`
on the destination file. Append removal notes to the result.

### Deriving the dotted module name

Convert `dest_file` (e.g. `"src/pkg/module.py"`) to dotted name (e.g. `"src.pkg.module"`):
```python
dest_module_dotted = dest_file.replace("/", ".").removesuffix(".py")
```

### New test

```python
def test_move_symbol_removes_self_import(tmp_path: Path) -> None:
    """After moving a symbol, self-referencing imports are removed from destination."""
```

This test needs a project structure where rope would generate a self-import. This
happens when moving a symbol to a module that is already imported by other modules —
rope adds an import of the destination module inside itself.

## ALGORITHM

```python
def _remove_self_imports(dest_path, dest_module_dotted):
    lines = dest_path.read_text().splitlines(keepends=True)
    removed = []
    kept = []
    for line in lines:
        stripped = line.strip()
        # Match: "import pkg.sub.module" or "from pkg.sub.module import ..."
        if (stripped == f"import {dest_module_dotted}"
            or stripped.startswith(f"from {dest_module_dotted} import ")):
            removed.append(stripped)
        else:
            kept.append(line)
    if removed:
        dest_path.write_text("".join(kept))
    return removed
```

## DATA

- `_remove_self_imports()` returns `list[str]` — the removed import lines
- These are included in the result string: `"Self-referencing import removed from [file]: [line]"`

## LLM PROMPT

```
Implement Step 3 from pr_info/steps/step_3.md (see pr_info/steps/summary.md for context).

Add _remove_self_imports() helper to rope_tools.py that removes import lines in the
destination file that reference the destination module itself. Call it from _move_symbol_impl()
after all moves complete (non-dry-run only). Include removed imports in the result output.

Add a test that verifies self-referencing imports are cleaned up after a move.

After making changes, run all three code quality checks (pylint, pytest unit tests, mypy).
Fix any issues before committing. Commit message: "feat(move_symbol): remove self-referencing imports after move"
```
