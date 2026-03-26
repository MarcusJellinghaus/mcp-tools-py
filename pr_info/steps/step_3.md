# Step 3: Batch move logic with all-or-nothing validation

> **Context**: See [summary.md](summary.md) for full issue overview.

## Goal

Implement the actual batch move loop in `_move_symbol_impl`: upfront validation of all
symbols, reverse-order iteration for correct ordering, and all-or-nothing failure semantics.

## WHERE

| File | Function/Section |
|------|-----------------|
| `src/mcp_tools_py/refactoring/rope_tools.py` | `_move_symbol_impl()` |
| `tests/test_refactoring/test_rope_tools.py` | New tests: batch move, ordering, validation |

## WHAT

### `_move_symbol_impl()` rewrite

The function currently processes `symbol_names[0]`. Replace with a loop that:

1. **Validates all symbols upfront** — before any rope operation
2. **Moves in reverse order** — so rope's prepend produces correct final ordering
3. **Collects results** — tracks what was moved and which files changed

```python
def _move_symbol_impl(
    project_dir: Path,
    source_file: str,
    symbol_names: list[str],
    dest_file: str,
    dry_run: bool,
) -> str:
```

### New tests

```python
def test_move_symbol_batch(sample_project: Path) -> None:
    """Move multiple symbols in one call, verify all arrive in destination."""

def test_move_symbol_batch_ordering(sample_project: Path) -> None:
    """Batch move preserves symbol order in destination file."""

def test_move_symbol_batch_validation_all_or_nothing(sample_project: Path) -> None:
    """If any symbol is invalid, no symbols are moved."""

def test_move_symbol_batch_collision_check(sample_project: Path) -> None:
    """If any symbol collides with destination, entire batch fails."""
```

## ALGORITHM

```python
# 1. UPFRONT VALIDATION (all-or-nothing)
source_text = read source file
for name in symbol_names:
    if _find_symbol_offset(source_text, name) is None:
        return error listing available symbols
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

**Key detail**: Each symbol move requires a fresh rope Project because rope caches file
contents. Re-reading source text and re-opening the project ensures rope sees the
updated file after each move.

## DATA

Return value is still `str`, but now includes per-symbol information:
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
Implement Step 3 from pr_info/steps/step_3.md (see pr_info/steps/summary.md for context).

Rewrite _move_symbol_impl() in rope_tools.py to support batch moves:
1. Upfront validation: verify all symbols exist and no collisions (fail entire call if any check fails)
2. Move symbols in reversed(symbol_names) order (rope prepends, so reverse gives correct order)
3. Each iteration: re-read source, re-open rope project (rope caches file contents)
4. Collect results across all moves

Add tests: batch move, ordering verification, all-or-nothing validation, batch collision.

After making changes, run all three code quality checks (pylint, pytest unit tests, mypy).
Fix any issues before committing. Commit message: "feat(move_symbol): batch move with all-or-nothing validation"
```
