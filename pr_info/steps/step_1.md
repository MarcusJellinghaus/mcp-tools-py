# Step 1: Thread `refactoring_timeout` from CLI to RefactoringTools

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

This step adds the `--refactoring-timeout` CLI argument and threads it through the
server → refactoring tools chain. No behavior change yet — just plumbing.

## WHERE: Files to modify

| File | Action |
|------|--------|
| `tests/test_refactoring/test_rope_tools.py` | Add test for timeout parameter acceptance |
| `tests/test_server.py` (or equivalent) | Add test for `refactoring_timeout` param in `CodeCheckerServer` |
| `src/mcp_tools_py/main.py` | Add `--refactoring-timeout` CLI argument |
| `src/mcp_tools_py/server.py` | Add `refactoring_timeout` param to `CodeCheckerServer` and `create_server` |
| `src/mcp_tools_py/refactoring/__init__.py` | Accept `timeout` in `RefactoringTools.__init__`, store as `self._timeout` |

## WHAT: Functions to modify

### `main.py::parse_args()`
Add argument:
```python
parser.add_argument(
    "--refactoring-timeout",
    type=int,
    default=120,
    help="Timeout in seconds for rope refactoring operations (default: 120)",
)
```

### `main.py::main()`
Pass to `create_server`:
```python
server = create_server(
    ...,
    refactoring_timeout=args.refactoring_timeout,
)
```

### `server.py::CodeCheckerServer.__init__()`
**Signature change**:
```python
def __init__(
    self,
    project_dir: Path,
    python_executable: Optional[str] = None,
    venv_path: Optional[str] = None,
    test_folder: str = "tests",
    keep_temp_files: bool = False,
    refactoring_timeout: int = 120,  # NEW
) -> None:
```
Store `self.refactoring_timeout = refactoring_timeout` and pass to `RefactoringTools`:
```python
RefactoringTools(self.project_dir, timeout=self.refactoring_timeout).register(self.mcp)
```

### `server.py::create_server()`
**Signature change**: Add `refactoring_timeout: int = 120` parameter, pass through.

### `refactoring/__init__.py::RefactoringTools.__init__()`
**Signature change**:
```python
def __init__(self, project_dir: Path, timeout: int = 120) -> None:
    self._project_dir = project_dir
    self._timeout = timeout
```

### `refactoring/__init__.py::_register_rope_tools()`
Capture `timeout = self._timeout` and pass to each rope function call:
```python
return rope_move_symbol(
    project_dir, source_file, symbol_name, dest_file, dry_run, timeout=timeout
)
```

## HOW: Integration points

- `main.py` → `server.py`: via `create_server()` keyword argument
- `server.py` → `refactoring/__init__.py`: via `RefactoringTools(project_dir, timeout=...)` constructor
- `refactoring/__init__.py` → `rope_tools.py`: via `timeout=` keyword on each public function

## ALGORITHM

```
1. parse_args() adds --refactoring-timeout (int, default=120)
2. main() passes args.refactoring_timeout to create_server()
3. CodeCheckerServer stores self.refactoring_timeout
4. CodeCheckerServer passes timeout to RefactoringTools(project_dir, timeout=...)
5. RefactoringTools stores self._timeout
6. Each registered rope tool closure passes timeout to rope_* function
```

## DATA

- `refactoring_timeout`: `int` (seconds), default `120`
- No new return types or data structures

## Tests (TDD — write first)

1. **Test CLI parsing**: Verify `parse_args()` returns `refactoring_timeout=120` by default
   and accepts `--refactoring-timeout 60`.
2. **Test server init**: Verify `CodeCheckerServer` stores `refactoring_timeout` attribute.
3. **Test RefactoringTools init**: Verify `RefactoringTools(path, timeout=60)._timeout == 60`.

## Commit message
```
Add --refactoring-timeout CLI arg and thread through server to RefactoringTools
```
