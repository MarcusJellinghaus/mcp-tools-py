# Step 2: Multiprocessing timeout wrapper + CLI plumbing

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

Add `--refactoring-timeout` CLI arg, thread it through server to rope functions,
and wrap each rope operation in a `multiprocessing.Process` for timeout protection.

## WHERE: Files to modify

| File | Action |
|------|--------|
| `src/mcp_tools_py/main.py` | Add `--refactoring-timeout` CLI argument |
| `src/mcp_tools_py/server.py` | Add `refactoring_timeout` param to `CodeCheckerServer` and `create_server` |
| `src/mcp_tools_py/refactoring/__init__.py` | Accept `timeout` in `RefactoringTools.__init__`, pass to rope functions |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Add `_run_with_timeout()`, split public functions into outer + `_*_impl` |
| `tests/test_refactoring/test_rope_tools.py` | Add timeout tests |

## WHAT: Functions to add/modify

### `main.py::parse_args()`
```python
parser.add_argument(
    "--refactoring-timeout",
    type=int,
    default=120,
    help="Timeout in seconds for rope refactoring operations (default: 120)",
)
```

### `main.py::main()`
Pass `refactoring_timeout=args.refactoring_timeout` to `create_server()`.

### `server.py::CodeCheckerServer.__init__()`
Add `refactoring_timeout: int = 120` parameter. Store and pass to `RefactoringTools`:
```python
RefactoringTools(self.project_dir, timeout=self.refactoring_timeout).register(self.mcp)
```

### `server.py::create_server()`
Add `refactoring_timeout: int = 120` parameter, pass through.

### `refactoring/__init__.py::RefactoringTools.__init__()`
```python
def __init__(self, project_dir: Path, timeout: int = 120) -> None:
    self._project_dir = project_dir
    self._timeout = timeout
```
Each rope tool closure passes `timeout=timeout` to the rope function.

### New: `rope_tools.py::_run_with_timeout()`
```python
def _run_with_timeout(
    func: Callable[..., str],
    args: tuple[Any, ...],
    timeout: int,
    operation_name: str,
) -> str:
```

### New: `rope_tools.py::_worker()`
```python
def _worker(
    queue: multiprocessing.Queue,  # type: ignore[type-arg]
    func: Callable[..., str],
    args: tuple[Any, ...],
) -> None:
```

### Refactored public functions

Each public function (`move_symbol`, `rename_symbol`, `move_module`) gains a
`timeout: int = 120` parameter. The rope `Project` logic is extracted into a
module-level `_*_impl` function:

- `_move_symbol_impl(project_dir, source_file, symbol_name, dest_file, dry_run) -> str`
- `_rename_symbol_impl(project_dir, file_path, symbol_name, new_name, dry_run) -> str`
- `_move_module_impl(project_dir, source_module, dest_package, dry_run) -> str`

The outer function does fast validation (file exists, symbol found), then calls
`_run_with_timeout(_*_impl, ...)`.

## HOW: Critical technical details

1. **Each `_*_impl` must create its own rope `Project` inside the subprocess**
   (including `ropefolder=None` and `ignored_resources`). Do NOT pass a `Project`
   object across process boundaries — it's not picklable.

2. **Call `queue.get(timeout=timeout)` BEFORE `process.join()`** to avoid Windows
   pipe deadlock. The queue result must be consumed before joining.

3. **`rope_tools.py` has no top-level side effects** — safe for Windows `spawn`
   re-import by `multiprocessing`.

4. **Timeout tests should use 3-5s timeout** with proper cleanup in a `finally`
   block calling `process.kill()` if the process is still alive.

5. **Inner `_*_impl` functions must be module-level** (not closures) for picklability
   by `multiprocessing`.

## ALGORITHM

### `_run_with_timeout()`
```
1. Create multiprocessing.Queue for result
2. Create Process(target=_worker, args=(queue, func, args))
3. process.start()
4. try: result = queue.get(timeout=timeout)  # get BEFORE join
5. except queue.Empty: → timeout path
6. process.join(timeout=5)
7. If process.is_alive(): process.kill(), process.join()
     → return "Error: {operation_name} timed out after {timeout}s. ..."
8. Return result
```

### `_worker()`
```
1. try: result = func(*args)
2. except Exception as exc: result = f"Error: {exc}"
3. queue.put(result)
```

### Data flow
```
CLI (--refactoring-timeout)
  → main.py (parse_args)
    → server.py (CodeCheckerServer.__init__)
      → refactoring/__init__.py (RefactoringTools.__init__)
        → rope_tools.py (each public function receives timeout param)
          → _run_with_timeout() (multiprocessing.Process wrapper)
            → _*_impl() (creates own Project, does rope work)
```

## DATA

- `refactoring_timeout` / `timeout`: `int` (seconds), default `120`
- Error format on timeout:
  ```
  Error: rename_symbol timed out after 120s.
  Parameters: file='models.py', symbol_name='MAX_NAME_LENGTH', new_name='NAME_MAX_CHARS'.
  Timeout: 120s
  ```

## Tests (TDD — write first)

1. **Test CLI parsing**: `parse_args()` returns `refactoring_timeout=120` by default
   and accepts `--refactoring-timeout 60`.

2. **Test RefactoringTools init**: `RefactoringTools(path, timeout=60)._timeout == 60`.

3. **Test timeout triggers**: Create a function that sleeps forever, pass to
   `_run_with_timeout()` with `timeout=3`. Assert returns error containing "timed out"
   and completes within ~5s. Use `finally` block with `process.kill()` for cleanup.

4. **Test normal operation with timeout**: Run `rename_symbol()` with `timeout=30`.
   Assert it succeeds normally.

5. **Test timeout error message format**: Verify error contains operation name and
   timeout value.

6. **Test existing rope tests still pass**: All existing tests must pass with the new
   `timeout` parameter defaulting to 120.

## Commit message
```
Add multiprocessing timeout wrapper and --refactoring-timeout CLI arg
```
