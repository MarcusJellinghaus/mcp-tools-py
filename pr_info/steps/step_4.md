# Step 4 — Real-run failure: report moved symbols, clean up if nothing moved

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_4.md` only. Use TDD: write the tests first, then the change. Run pylint, pytest (`-n auto`) and mypy through the MCP tools and make them pass. Run `run_format_code`, then make one commit.

## WHERE

- `src/mcp_tools_py/refactoring/rope_tools.py`
- `tests/test_refactoring/test_rope_tools.py`

## WHAT

```python
_MOVE_SUCCESS_PREFIX = "move_symbol completed successfully."

def _split_moved(
    project_dir: Path, source_file: str, dest_file: str, names: list[str]
) -> tuple[list[str], list[str]]: ...
```

Then extend `move_symbol(...)`.

## ALGORITHM

`_split_moved`:
```
src_syms = _get_top_level_symbols(read(source)) if source exists else []
dst_syms = _get_top_level_symbols(read(dest)) if dest exists else []
moved = [n for n in names if n not in src_syms and n in dst_syms]
not_moved = [n for n in names if n not in moved]
```

Treat an `OSError` or `UnicodeDecodeError` on read as empty text.

`move_symbol`, after `_run_rope_subprocess`:
```
if dry_run: _remove_new_paths(snapshot); return result
if result.startswith(_MOVE_SUCCESS_PREFIX): return result
moved, not_moved = _split_moved(...)
if not moved: _remove_new_paths(snapshot)
if result.startswith("Error"): result += listing(moved, not_moved)
return result
```

## HOW

- Use `_MOVE_SUCCESS_PREFIX` in `_move_symbol_impl`'s success line as well, so there's a single source of truth.
- Delete `created_dest` and the remaining `_cleanup_created_files` call in `_move_symbol_impl`. Then delete the `_cleanup_created_files` function. Keep `_cleanup_empty_dirs`, which `_cleanup_package` uses.
- Validation errors don't start with `Error`, so they come back unchanged. Their cleanup does nothing.

## DATA

The listing is appended to the original error text:

```
<original error>
Rope changes cannot be rolled back.
  Moved: a, b
  Not moved: c
The state of the symbol in flight is uncertain; check `git diff`.
```

Print `(none)` for an empty list.

## Tests

These reuse the fake `execute_command` from step 3.

- `test_move_symbol_real_timeout_lists_moved`: the fake rewrites `src/foo.py` without `my_func`, writes `src/baz.py` containing `def my_func(): ...`, then reports a timeout. Call `move_symbol(..., ["my_func", "MyClass"], "src/baz.py")`. The result contains `timed out`, `Moved: my_func`, `Not moved: MyClass` and `git diff`, and `src/baz.py` still exists.
- `test_move_symbol_real_failure_nothing_moved_cleans_up`: the fake creates `src/sub/new.py` and `src/sub/__init__.py`, then reports a timeout. Run a real move into `src/sub/new.py`. `src/sub` no longer exists, and the result contains `Moved: (none)`.
- The existing validation tests (not found, collision, duplicates) keep passing unchanged.
