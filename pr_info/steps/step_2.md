# Step 2: Batch signature change (`symbol_name` → `symbol_names`)

> **Context**: See [summary.md](summary.md) for full issue overview.

## Goal

Change `move_symbol` to accept `symbol_names: list[str]` instead of `symbol_name: str`.
Clean break — update all callers and tests. This step only changes the plumbing; the
actual batch loop logic comes in Step 3.

In this step, `_move_symbol_impl` still moves **one symbol at a time** but receives a
list and processes `symbol_names[0]` — the loop is added in Step 3.

**Important**: This is a transitional step. The impl takes a list but only handles
single-element lists. Step 3 adds the real batch logic.

## WHERE

| File | Function/Section |
|------|-----------------|
| `src/mcp_tools_py/refactoring/rope_tools.py` | `move_symbol()`, `_move_symbol_impl()` |
| `src/mcp_tools_py/refactoring/rope_cli.py` | `main()` — move_symbol dispatch |
| `src/mcp_tools_py/refactoring/__init__.py` | `_register_rope_tools()` — `move_symbol` tool |
| `tests/test_refactoring/test_rope_tools.py` | All `move_symbol` test calls |
| `tests/test_refactoring/test_integration.py` | All `move_symbol` test calls |

## WHAT

### `rope_tools.py` — `move_symbol()` (public API)

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

### `rope_tools.py` — `_move_symbol_impl()` (subprocess impl)

```python
def _move_symbol_impl(
    project_dir: Path,
    source_file: str,
    symbol_names: list[str],  # CHANGED from symbol_name: str
    dest_file: str,
    dry_run: bool,
) -> str:
```

For now, operates on `symbol_names[0]` only (same logic as before, just reading from
the list). The batch loop is Step 3.

### `rope_cli.py` — dispatch

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

### `__init__.py` — tool registration

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

### Test updates

Every test call that passes `symbol_name="X"` or positional `"X"` becomes
`symbol_names=["X"]` or `["X"]`. Mechanical find-and-replace.

## ALGORITHM

```
1. In move_symbol(): change param name, pass list in args dict
2. In _move_symbol_impl(): change param name, use symbol_names[0] for now
3. In rope_cli.py: change args["symbol_name"] → args["symbol_names"]
4. In __init__.py: change tool param name and docstring
5. In all tests: wrap single symbol in list
```

## DATA

- Args dict key changes from `"symbol_name"` (str) to `"symbol_names"` (list[str])
- Return values unchanged

## LLM PROMPT

```
Implement Step 2 from pr_info/steps/step_2.md (see pr_info/steps/summary.md for context).

Change move_symbol signature from symbol_name: str to symbol_names: list[str] across
all layers: rope_tools.py (both move_symbol and _move_symbol_impl), rope_cli.py,
__init__.py, and ALL test files (test_rope_tools.py, test_integration.py).

For now, _move_symbol_impl should just use symbol_names[0] — the batch loop comes later.
This is a mechanical signature change only.

After making changes, run all three code quality checks (pylint, pytest unit tests, mypy).
Fix any issues before committing. Commit message: "refactor(move_symbol): change symbol_name to symbol_names list"
```
