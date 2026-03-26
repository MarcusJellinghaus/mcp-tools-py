# Issue #120: move_symbol — from-global imports, self-import removal, batch moves

## Overview

Enhance `move_symbol` to support batch moves, use `from X import Y` import style, and
clean up self-referencing imports that rope leaves behind. Improve result output with
review reminders.

## Architectural / Design Changes

### 1. Rope Project Configuration (global)

`_with_rope_project()` gains a `preferred_import_style = "from-global"` preference.
This affects **all** rope operations (move_symbol, move_module, rename_symbol) — rope
will generate `from pkg.mod import symbol` instead of `import pkg.mod` with fully-qualified
usage. This is a one-line change in the context manager.

### 2. API Signature Change (breaking)

`move_symbol` changes from single-symbol to batch:

```
# Before
move_symbol(project_dir, source_file, symbol_name: str, dest_file, ...)

# After
move_symbol(project_dir, source_file, symbol_names: list[str], dest_file, ...)
```

Clean break — no backward compatibility shim. All callers updated.

The JSON protocol between `move_symbol()` → `rope_cli.py` → `_move_symbol_impl()`
changes the key from `"symbol_name"` to `"symbol_names"` (list).

### 3. Validation Strategy (all-or-nothing)

Before any rope operation, validate **all** symbols upfront:
- No duplicates within `symbol_names`
- Each symbol exists in source (via `_find_symbol_offset`)
- No name collisions in destination (via `_get_top_level_symbols`)

If any validation check fails, the entire call fails with no partial moves.

**Scope**: The all-or-nothing guarantee applies to **validation only**. If a runtime
rope error occurs during the actual move loop after validation passes (e.g., the 2nd
symbol fails after the 1st has been moved), there is no rollback. This is acceptable
because upfront validation already confirmed all symbols exist and no collisions are
present, making runtime errors unlikely.

### 4. Move Ordering

Symbols are moved in **reverse order** internally. Rope prepends moved symbols to the
destination file, so reversing the iteration produces the correct final ordering
(symbols appear in the destination in the same order they were listed).

### 5. Self-Import Removal (post-processing)

After all moves complete, scan the destination file for import lines referencing the
destination module itself. Remove them unconditionally — a module importing itself is
always a rope artifact. Simple line-level string matching (no AST needed).

### 6. Result Output

Structured result string with:
- Per-symbol move summary
- Files modified/created
- Self-import removal notes (if applicable)
- Review reminders (absolute imports, symbol order)

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/refactoring/rope_tools.py` | `_with_rope_project()` preference, `_move_symbol_impl()` rewrite for batch+self-import, `move_symbol()` signature change |
| `src/mcp_tools_py/refactoring/rope_cli.py` | JSON dispatch: `symbol_name` → `symbol_names` |
| `src/mcp_tools_py/refactoring/__init__.py` | Tool registration: `symbol_name` → `symbol_names` |
| `tests/test_refactoring/test_rope_tools.py` | Update existing tests, add batch/self-import/from-global/validation tests |
| `tests/test_refactoring/test_integration.py` | Update integration tests for new signature |
| `tests/mcp_tools_py_manual/TEST_PLAN.md` | Update Tests 7a–7c for new signature, add Tests 7d–7f for batch moves |

## Files NOT Modified

- `rope_tools.py`: `_rename_symbol_impl`, `_move_module_impl` — unchanged (benefit from `from-global` automatically)
- `jedi_tools.py` — unrelated
- `subprocess_runner.py` — unrelated

## Implementation Steps

| Step | Commit | Description |
|------|--------|-------------|
| 1 | `from-global` preference | Set `preferred_import_style` in `_with_rope_project()` + test |
| 2 | Batch move_symbol | Signature change (`symbol_name` → `symbol_names`), batch loop with reverse-order iteration, all-or-nothing validation (duplicates, existence, collisions), update all existing tests + new batch tests |
| 3 | Self-import removal | Post-move cleanup of self-referencing imports + test |
| 4 | Result output + review reminders | Structured output with notes + test |
| 5 | Manual test plan update | Update Tests 7a–7c for new signature, add Tests 7d–7f for batch moves |
