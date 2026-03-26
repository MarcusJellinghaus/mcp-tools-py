# Step 2: Batch move_symbol — signature change, loop, and validation

> **Context**: See [summary.md](summary.md) for full issue overview.

## Goal

**Note**: This step is intentionally large because the signature change must be atomic across all layers and tests to keep checks green.

Change `move_symbol` from single-symbol to batch: update the signature from
`symbol_name: str` to `symbol_names: list[str]` across all layers, implement
the batch loop with reverse-order iteration, and add all-or-nothing upfront
validation. Update all existing tests and add new batch tests.

## WHERE

| File | Function/Section |
|------|-----------------|
| `src/mcp_tools_py/refactoring/rope_tools.py` | `move_symbol()`, `_move_symbol_impl()` |
| `src/mcp_tools_py/refactoring/rope_cli.py` | `main()` — move_symbol dispatch |
| `src/mcp_tools_py/refactoring/__init__.py` | `_register_rope_tools()` — `move_symbol` tool |
| `tests/test_refactoring/test_rope_tools.py` | Update existing tests + new batch tests |
| `tests/test_refactoring/test_integration.py` | Update existing tests for new signature |

## WHAT

### Signature change across all layers

#### `rope_tools.py` — `move_symbol()` (public API)

```python
def move_symbol(
    project_dir: Path,
    source_file: str,
    symbol_names: list[str],  # CHANGED from symbol_name: str
    dest_file: str,
    dry_run: bool = False,
    timeout: int = 120,
) -> str:
```

Passes `"symbol_names": symbol_names` in the args dict (was `"symbol_name"`).

#### `rope_tools.py` — `_move_symbol_impl()` (subprocess impl)

```python
def _move_symbol_impl(
    project_dir: Path,
    source_file: str,
    symbol_names: list[str],  # CHANGED from symbol_name: str
    dest_file: str,
    dry_run: bool,
) -> str:
```

#### `rope_cli.py` — dispatch

```python
elif operation == "move_symbol":
    result = _move_symbol_impl(
        project_dir,
        args["source_file"],
        args["symbol_names"],   # CHANGED from args["symbol_name"]
        args["dest_file"],
        args["dry_run"],
    )
```

#### `__init__.py` — tool registration

```python
def move_symbol(
    source_file: str,
    symbol_names: list[str],  # CHANGED from symbol_name: str
    dest_file: str,
    dry_run: bool = False,
) -> str:
    """Move top-level functions, classes, or variables to another module.
    Updates all imports project-wide. Auto-creates destination file and
    missing __init__.py files if needed.

    Args:
        source_file: Source file path relative to project root.
        symbol_names: Names of top-level symbols to move.
        dest_file: Destination file path relative to project root.
        dry_run: Preview changes without applying (default: False).
    """
    return rope_move_symbol(
        project_dir,
        source_file,
        symbol_names,
        dest_file,
        dry_run,
        timeout=timeout,
    )
```

### Batch move logic in `_move_symbol_impl()`

Implement the full batch loop: upfront validation, reverse-order iteration,
per-symbol rope operations.

### Existing test updates

Every test call that passes `symbol_name="X"` or positional `"X"` becomes
`symbol_names=["X"]` or `["X"]`. Mechanical find-and-replace.

### New tests

```python
def test_move_symbol_batch(sample_project: Path) -> None:
    """Move multiple symbols in one call, verify all arrive in destination."""

def test_move_symbol_batch_ordering(sample_project: Path) -> None:
    """Batch move preserves symbol order in destination file."""

def test_move_symbol_batch_validation_all_or_nothing(sample_project: Path) -> None:
    """If any symbol fails validation (doesn't exist, collision, duplicate), no symbols are moved."""

def test_move_symbol_batch_collision_check(sample_project: Path) -> None:
    """If any symbol collides with destination, entire batch fails."""
```

## ALGORITHM

```python
# 1. UPFRONT VALIDATION (all-or-nothing)
source_text = read source file

# 1a. Duplicate check
if len(symbol_names) != len(set(symbol_names)):
    return error about duplicate symbol names

# 1b. Existence check
for name in symbol_names:
    if _find_symbol_offset(source_text, name) is None:
        return error listing available symbols

# 1c. Collision check
if dest exists:
    dest_symbols = _get_top_level_symbols(dest_text)
    for name in symbol_names:
        if name in dest_symbols:
            return collision error

# 2. CREATE DEST IF NEEDED (same as before, once)
ensure_parents + create empty dest if not exists

# 3. MOVE EACH SYMBOL IN REVERSE ORDER
results = []
for name in reversed(symbol_names):
    # Re-read source each iteration (rope modifies it)
    source_text = read source file
    offset = _find_symbol_offset(source_text, name)
    with _with_rope_project(project_dir) as project:
        mover = create_move(project, source_resource, offset)
        changes = mover.get_changes(dest_resource)
        if not dry_run:
            project.do(changes)
        results.append((name, changes))

# 4. RETURN combined result
```

### Dry-run with batch moves

For dry-run mode: create the dest file once (if needed), loop through all
symbols accumulating change previews, then clean up the temp dest file once
at the end. This avoids creating/cleaning temp files per symbol.

In dry-run mode, source is not modified between iterations since `project.do()` is not called. Each symbol still needs its own rope Project instance and `_find_symbol_offset` call on the unchanged source text. The preview for each symbol shows what would change independently.

### "All-or-nothing" scope

The all-or-nothing guarantee applies to **validation only**: symbol existence,
collision checks, and duplicate checks. If validation passes and a runtime
rope error occurs during the actual move loop (e.g., the 2nd symbol fails
after the 1st has been moved), there is no rollback — the moves that
succeeded remain applied. This is acceptable because upfront validation
already confirmed all symbols exist and no collisions are present, making
runtime errors unlikely.

The existing `_cleanup_created_files()` logic (which only deletes empty files) handles partial batch failures correctly — after successful moves, the dest file has content and won't be deleted. Move the `created_dest` flag and exception handling outside the per-symbol loop.

**Key detail**: Each symbol move requires a fresh rope Project because rope caches file
contents. Re-reading source text and re-opening the project ensures rope sees the
updated file after each move.

## DATA

- Args dict key changes from `"symbol_name"` (str) to `"symbol_names"` (list[str])
- Return value is still `str`, but now includes per-symbol information:
```
move_symbol completed successfully.
  Moved: my_func, MyClass, MY_VAR
  Modified: src/foo.py
  Modified: src/bar.py
  Created: src/baz.py
```

For dry-run, each symbol's changes are previewed.

## LLM PROMPT

```
Implement Step 2 from pr_info/steps/step_2.md (see pr_info/steps/summary.md for context).

This step combines signature change + batch loop + validation into one commit:

1. Change move_symbol signature from symbol_name: str to symbol_names: list[str] across
   all layers: rope_tools.py (both move_symbol and _move_symbol_impl), rope_cli.py,
   __init__.py, and ALL test files (test_rope_tools.py, test_integration.py).

2. Implement _move_symbol_impl() batch logic:
   - Duplicate check: reject lists with repeated symbol names
   - Existence check: verify all symbols exist in source (fail entire call if any missing)
   - Collision check: verify no name collisions in destination (fail entire call if any)
   - Move in reversed(symbol_names) order (rope prepends, so reverse gives correct order)
   - Each iteration: re-read source, re-open rope project (rope caches file contents)
   - Dry-run: create dest once, accumulate previews, clean up once at end

3. Update all existing tests to use symbol_names=[...] syntax.

4. Add new tests: batch move, ordering, all-or-nothing validation (tests validation
   failures, not runtime errors), collision check.

Note: Update error messages to reference the specific symbol name from the loop iteration
variable, not the entire `symbol_names` list. E.g., `f"Error moving '{name}': {exc}"`.

After making changes, run all three code quality checks (pylint, pytest unit tests, mypy).
Fix any issues before committing. Commit message: "feat(move_symbol): batch move with signature change and validation"
```
