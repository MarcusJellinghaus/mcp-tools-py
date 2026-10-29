# Step 3 — Parent-side snapshot cleanup for dry runs

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_3.md` only. Use TDD: write the tests first, then the change. Run pylint, pytest (`-n auto`) and mypy through the MCP tools and make them pass. Run `run_format_code`, then make one commit.

## WHERE

- `src/mcp_tools_py/refactoring/rope_tools.py`
- `tests/test_refactoring/test_rope_tools.py`

## WHAT

```python
def _missing_paths(project_dir: Path, dest_file: str) -> list[Path]: ...
def _remove_new_paths(paths: list[Path]) -> None: ...
```

Then change `move_symbol(...)`, the module-level function, so it calls both around `_run_rope_subprocess`.

## ALGORITHM

`_missing_paths`:
```
paths = [abs_dest] if not abs_dest.exists() else []
current = abs_dest.parent
while current != project_dir and current.is_relative_to(project_dir):
    for p in (current / "__init__.py", current): append p if not p.exists()
    current = current.parent
return paths   # already ordered deepest first, files before their dir
```

`_remove_new_paths`: for each `p` in order:
- If it's a file, unlink it.
- If it's a dir and empty, `rmdir` it.
- Skip anything else.

Wrap each operation in a short retry for `PermissionError` (about 5 tries, `time.sleep(0.2)`), because on Windows a just-killed child may still hold handles. After the last try, log a warning and continue.

`move_symbol`:
```
snapshot = _missing_paths(project_dir, dest_file)
result = _run_rope_subprocess(...)
if dry_run: _remove_new_paths(snapshot)
return result
```

## HOW

- In `_move_symbol_impl`, remove `created_for_dry_run` and both `_cleanup_created_files(..., created_for_dry_run, ...)` calls for dry runs. The dry-run branch still calls `_ensure_parents` and writes the empty destination, which rope needs.
- Keep the real-run `created_dest` cleanup for now. Step 4 removes it.
- `_cleanup_empty_dirs` stays as it is.
- `time` is a new stdlib import.

## DATA

`_missing_paths` returns an ordered `list[Path]` of absolute paths that don't exist before the call.

## Tests

The fake subprocess is `mcp_tools_py.refactoring.rope_tools.execute_command`, monkeypatched to return `CommandResult(return_code=-1, stdout="", stderr="", timed_out=True)` from `mcp_tools_py.utils.subprocess_runner`. Write a small helper or factory in the test file that later steps can reuse. It takes a side-effect callable that runs before returning.

- `test_move_symbol_dry_run_timeout_leaves_no_files`: the fake creates `src/sub/new.py` and `src/sub/__init__.py`, then reports a timeout. After `move_symbol(..., "src/sub/new.py", dry_run=True)`, `src/sub` doesn't exist, and the result contains `timed out`.
- `test_move_symbol_dry_run_existing_dir_no_stray_init`: create `src/plain/` holding only `other.txt`, with no `__init__.py`. Run a real dry run of `my_func` into `src/plain/new.py`. Afterwards `src/plain/__init__.py` and `src/plain/new.py` don't exist, and `other.txt` is still there.
- Update `test_move_symbol_attribute_error_hint`: it calls `_move_symbol_impl` directly, and the child no longer cleans up. Remove the last assertion, the one checking that `baz.py` doesn't exist. `test_move_symbol_dry_run` already covers parent-side cleanup.
