# Step 3: Replace multiprocessing with subprocess isolation

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

## Problem with Step 2 (multiprocessing)

The `multiprocessing.Process` + `Queue` approach from Step 2 failed in the MCP
server context:

1. **Windows `spawn` inherits MCP stdio pipes** — child processes inherit the
   parent's stdin/stdout file handles. Since MCP uses stdin/stdout for JSON-RPC
   communication, the child process's rope operations interfered with the
   transport layer.

2. **`anyio.to_thread.run_sync()` also failed** — even offloading to a thread
   pool didn't help because the MCP SDK's `func_metadata.py` calls sync tool
   functions directly in the event loop (lines 92-95), and something about the
   process environment itself caused rope to block.

3. **Rope works fine in isolation** — CLI tests and pytest both complete in <1s.
   The hang is purely a MCP server process context issue.

## Solution: Subprocess isolation (same pattern as pytest/pylint/mypy)

The project already has a proven pattern in `subprocess_runner.py` that runs
pytest, pylint, and mypy in isolated subprocesses with:
- `stdin=DEVNULL` (prevents MCP pipe inheritance)
- File-based stdout/stderr isolation for Python commands
- Proper timeout handling with Windows process tree cleanup via `taskkill`
- `get_python_isolation_env()` that strips MCP environment variables

We follow this exact pattern for rope operations.

## Architecture

```
MCP tool call (sync function in __init__.py)
  → rope_tools.py::rename_symbol()  (public API)
    → _run_rope_subprocess()
      → execute_command([python, -m, rope_cli, operation, json_args])
        → subprocess_runner.py (stdin=DEVNULL, file-based stdout)
          → rope_cli.py::main()  (completely isolated process)
            → _rename_symbol_impl()  (actual rope work)
              → JSON result on stdout
```

### New file: `rope_cli.py`

CLI entry point that accepts `<operation> <json_args>`, dispatches to the
appropriate `_*_impl` function, and outputs the result as JSON on stdout.

### Modified: `rope_tools.py`

- Removed: `_run_with_timeout()`, `_worker()`, `multiprocessing` imports
- Added: `_run_rope_subprocess()` using `execute_command` from `subprocess_runner.py`
- Public functions now delegate to `_run_rope_subprocess()` instead of
  `_run_with_timeout()`
- `_*_impl` functions unchanged — they contain the actual rope logic

### Modified: `__init__.py`

- Reverted from `async def` + `anyio.to_thread.run_sync()` back to sync `def`
- Restored `@log_function_call` decorators
- Subprocess isolation makes async wrapping unnecessary — the subprocess call
  is fast (returns in ~1-2s) and doesn't block the event loop

## Why subprocess over multiprocessing

| Aspect | multiprocessing | subprocess |
|--------|----------------|------------|
| Pipe inheritance | Inherits parent stdin/stdout | `stdin=DEVNULL`, file-based stdout |
| MCP compatibility | Breaks MCP stdio transport | Fully isolated |
| Proven in project | No | Yes (pytest/pylint/mypy use same pattern) |
| Windows support | `spawn` causes issues | `taskkill /T` for cleanup |
| Complexity | Queue + Process + join ordering | Single `execute_command` call |

## Files modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/refactoring/rope_cli.py` | NEW — CLI entry point |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Replace multiprocessing with `_run_rope_subprocess()` |
| `src/mcp_tools_py/refactoring/__init__.py` | Revert to sync tools, restore `@log_function_call` |
| `tests/test_refactoring/test_integration.py` | Add hang-regression tests + real project dir tests |
| `tests/test_refactoring/test_rope_tools.py` | Remove multiprocessing timeout tests |

## Commit
```
fix(refactoring): run rope in subprocess to prevent MCP hang
```
