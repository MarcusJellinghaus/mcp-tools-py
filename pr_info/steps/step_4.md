# Step 4: Multiprocessing timeout wrapper for rope operations

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

This step wraps each rope operation in a `multiprocessing.Process` so it can be cleanly
killed on timeout. This is the core fix — if rope hangs, the MCP server recovers after
the timeout instead of blocking indefinitely.

## WHERE: Files to modify

| File | Action |
|------|--------|
| `tests/test_refactoring/test_rope_tools.py` | Add timeout behavior tests |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Add `_run_with_timeout()`, wrap public functions |

## WHAT: Functions to add/modify

### New: `rope_tools.py::_run_with_timeout()`

```python
def _run_with_timeout(
    func: Callable[..., str],
    args: tuple[Any, ...],
    timeout: int,
    operation_name: str,
) -> str:
    """Run a function in a subprocess with timeout protection.

    Args:
        func: The function to execute (must be picklable — module-level).
        args: Positional arguments for func.
        timeout: Maximum seconds to wait.
        operation_name: Name for error messages (e.g. "rename_symbol").

    Returns:
        The string result from func, or an error message on timeout/failure.
    """
```

### New: `rope_tools.py::_worker()`

```python
def _worker(
    queue: multiprocessing.Queue[str],
    func: Callable[..., str],
    args: tuple[Any, ...],
) -> None:
    """Target for multiprocessing.Process — runs func and puts result in queue."""
```

### Modified: `rope_tools.py::move_symbol()`, `rename_symbol()`, `move_module()`

Each gains a `timeout: int = 120` parameter. The function body is split into:
- **Outer function** (existing name): Validates inputs (file exists, symbol found),
  then calls `_run_with_timeout()` with the rope operation.
- **Inner operation** (new `_move_symbol_impl`, `_rename_symbol_impl`, `_move_module_impl`):
  Contains the rope `Project` + `get_changes()` + `project.do()` logic.

The inner functions must be module-level (not closures) so they're picklable by
`multiprocessing`.

## HOW: Integration points

- `import multiprocessing` — stdlib, no new dependency
- `_run_with_timeout()` is called by each of the 3 public functions
- The `timeout` parameter flows from `RefactoringTools._timeout` (set up in Step 1)
- Each `_*_impl()` function receives `project_dir`, operation-specific args, and returns `str`

## ALGORITHM

### `_run_with_timeout()`
```
1. Create multiprocessing.Queue for result
2. Create Process(target=_worker, args=(queue, func, args))
3. process.start()
4. process.join(timeout=timeout)
5. If process.is_alive(): process.terminate(), join(5), process.kill() if still alive
     → return error: "Error: {operation_name} timed out after {timeout}s.
        Parameters: {args}. Timeout: {timeout}s"
6. If queue not empty: return queue.get()
7. Else: return error about unexpected failure (process died without result)
```

### `_worker()`
```
1. try: result = func(*args)
2. except Exception as exc: result = f"Error: {exc}"
3. queue.put(result)
```

### Refactored `rename_symbol()` (example pattern for all three)
```
1. Validate file exists, find symbol offset (fast, no timeout needed)
2. If validation fails: return error immediately
3. Call _run_with_timeout(_rename_symbol_impl, (project_dir, file_path, offset, new_name, dry_run), timeout, "rename_symbol")
4. Return result
```

## DATA

- **Input**: `timeout: int` (seconds) on each public function
- **Output**: Unchanged — all functions still return `str`
- **Error format on timeout**:
  ```
  Error: rename_symbol timed out after 120s.
  Parameters: file='models.py', symbol_name='MAX_NAME_LENGTH', new_name='NAME_MAX_CHARS'.
  Timeout: 120s
  ```
  (operation name, parameters, timeout value — no suggestions, per issue spec)

## Tests (TDD — write first)

1. **Test timeout triggers**: Mock/create a function that sleeps forever, pass to
   `_run_with_timeout()` with timeout=2. Assert returns error containing "timed out"
   and completes within ~3s.

2. **Test normal operation with timeout**: Run `rename_symbol()` with `timeout=30` on the
   existing `sample_project` fixture. Assert it succeeds normally (timeout doesn't
   interfere with fast operations).

3. **Test timeout error message format**: Verify the error message contains operation name,
   and timeout value.

4. **Test existing rope tests still pass**: All existing `test_rope_tools.py` tests must
   continue to pass with the new `timeout` parameter defaulting to 120.

## Commit message
```
Add multiprocessing timeout wrapper for rope operations to prevent indefinite hangs
```
